import os
import re
from collections import defaultdict
import logging

# Set up logging for the dynamic build process
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from error_parser import (
    BRACE_MATCH, N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

class N64PatchEngine:
    def __init__(self):
        self.fixes_count = 0
        self.modified_files = set()

    def deterministic_hash(self, name):
        """Generates a stable unique ID for macros to prevent switch-case collisions."""
        h = 0
        for c in name: h = (31 * h + ord(c)) & 0xFFFFFFFF
        return (h % 80000) + 2000

    def ensure_base_types(self):
        """Maintains the core foundation of the AArch64 port."""
        primitives = """
#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
#include <stdint.h>
#include <string.h>
#include <math.h>

typedef uint8_t u8;   typedef int8_t s8;
typedef uint16_t u16; typedef int16_t s16;
typedef uint32_t u32; typedef int32_t s32;
typedef uint64_t u64; typedef int64_t s64;
typedef float f32;    typedef double f64;
typedef int n64_bool;

typedef u32 OSIntMask; typedef u64 OSTime;
typedef u32 OSId;      typedef s32 OSPri;
typedef void* OSMesg;

/* SDK Audio/Gfx State Structs - Aligned for AArch64 */
typedef struct { long long int data[16]; } RESAMPLE_STATE;
typedef struct { long long int data[16]; } ENVMIX_STATE;

#ifndef OS_READ
  #define OS_READ 0
  #define OS_WRITE 1
#endif
#endif
"""
        content = read_file(TYPES_HEADER) if os.path.exists(TYPES_HEADER) else ""
        if "CORE_PRIMITIVES_DEFINED" not in content:
            new_content = "#pragma once\n" + primitives + "\n" + content.replace("#pragma once", "")
            write_file(TYPES_HEADER, new_content)
            logging.info("Foundation Established: Core Primitive Layer injected.")

    def promote_or_inject_member(self, struct_name, member_name, context_line=""):
        """
        DYNAMISM: Upgrades types from scalars to pointers/arrays if the code context requires it.
        """
        content = read_file(TYPES_HEADER)
        
        # Inference Heuristic: Determine type from usage
        target_type = "long long int"
        if "->" in context_line or "*" in context_line or "ptr" in member_name.lower(): 
            target_type = "void*"
        elif "[" in context_line or any(x in member_name.lower() for x in ["id", "buf", "name", "data"]):
            target_type = "u8[256]"

        struct_pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"
        match = re.search(struct_pattern, content)
        
        if match:
            header, body, footer = match.groups()
            # PROMOTION: If it exists as a scalar but code tries to use it as a pointer/array
            if f" {member_name};" in body:
                if target_type == "void*" and "long long int" in body:
                    body = body.replace(f"long long int {member_name};", f"void* {member_name}; /* PROMOTED */")
                    logging.info(f"Promoted {struct_name}.{member_name} to Pointer.")
                elif "u8[" in target_type and "long long int" in body:
                    body = body.replace(f"long long int {member_name};", f"u8 {member_name}[256]; /* PROMOTED */")
                    logging.info(f"Promoted {struct_name}.{member_name} to Array.")
            elif f" {member_name}" not in body:
                # INJECTION: Add the member if missing
                decl = f"    void* {member_name}; /* AUTO-PTR */" if target_type == "void*" else \
                       (f"    u8 {member_name}[256]; /* AUTO-ARR */" if "u8[" in target_type else f"    long long int {member_name};")
                body = body.rstrip() + f"\n{decl}\n"
                logging.info(f"Injected {struct_name}.{member_name} as {target_type}.")
            
            new_content = content[:match.start()] + header + body + footer + content[match.end():]
            write_file(TYPES_HEADER, new_content)
            self.fixes_count += 1

    def handle_global_promotion(self, var_name, context_line=""):
        """Upgrades global externs if they are accessed like objects/arrays."""
        content = read_file(TYPES_HEADER)
        if "->" in context_line or "[" in context_line:
            old_decl = f"extern long long int {var_name};"
            new_decl = f"extern void* {var_name}; /* PROMOTED */"
            if old_decl in content:
                write_file(TYPES_HEADER, content.replace(old_decl, new_decl))
                logging.info(f"Promoted Global Extern '{var_name}' to Pointer.")
                self.fixes_count += 1

    def run_cycle(self, categories):
        self.ensure_base_types()

        # 1. Surgical Fixes (High-risk syntax fixes)
        for cat in ["expected_expression", "redefinition"]:
            for filepath, data in categories.get(cat, []):
                if not os.path.exists(filepath): continue
                content = read_file(filepath)
                if cat == "expected_expression":
                    # Fix: n64_memcpy(dest, {literal}, size) -> n64_memcpy(dest, (f32[]){literal}, size)
                    content = re.sub(r'n64_memcpy\s*\(([^,]+),\s*\{([^}]+)\},\s*([^)]+)\)', 
                                     r'n64_memcpy(\1, (f32[]){\2}, \3)', content)
                elif cat == "redefinition":
                    content = re.sub(rf"^(.*?\b{re.escape(data)}\b.*?;)", r"/* AUTO-REDEF */ // \1", content, flags=re.MULTILINE)
                write_file(filepath, content)
                self.modified_files.add(filepath); self.fixes_count += 1

        # 2. Dynamic Structural Fixes
        for struct_name, member_name in categories.get("missing_members", []):
            self.promote_or_inject_member(struct_name, member_name, context_line=member_name)

        for filepath, glob in categories.get("missing_globals", []):
            self.handle_global_promotion(glob, context_line=glob)
            types_content = read_file(TYPES_HEADER)
            if f" {glob};" not in types_content:
                types_content += f"\n#ifndef {glob}_DEFINED\nextern long long int {glob};\n#define {glob}_DEFINED\n#endif"
                write_file(TYPES_HEADER, types_content)

        # 3. Type Discovery & SDK Body Injection
        types_content = read_file(TYPES_HEADER)
        for filepath, tag in categories.get("missing_types", []):
            if tag in N64_STRUCT_BODIES:
                if f"struct {tag}" not in types_content:
                    types_content += "\n" + N64_STRUCT_BODIES[tag]
                    self.fixes_count += 1
            elif tag not in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg", "RESAMPLE_STATE", "ENVMIX_STATE"]:
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                if f"struct {struct_tag}" not in types_content:
                    types_content += f"\nstruct {struct_tag} {{ long long int pad[64]; }};\ntypedef struct {struct_tag} {tag};"
                    self.fixes_count += 1
            
            # Ensure the source file knows about our types
            if filepath and os.path.exists(filepath) and "n64_types.h" not in read_file(filepath):
                write_file(filepath, '#include "ultra/n64_types.h"\n' + read_file(filepath))

        # 4. Conflict Resolution (POSIX Renaming)
        seen_static = set()
        for cat in ["static_conflict", "posix_reserved_conflict"]:
            for filepath, func_name in categories.get(cat, []):
                if (filepath, func_name) in seen_static or not os.path.exists(filepath): continue
                seen_static.add((filepath, func_name))
                content = read_file(filepath)
                prefix = os.path.basename(filepath).split('.')[0]
                macro = f"\n/* AUTO: POSIX Conflict Fix */\n#define {func_name} n64_renamed_{prefix}_{func_name}\n"
                if macro not in content:
                    anchor = '#include "ultra/n64_types.h"'
                    content = content.replace(anchor, anchor + macro) if anchor in content else macro + content
                    write_file(filepath, content); self.modified_files.add(filepath); self.fixes_count += 1

        # 5. Deterministic Macro Injection
        types_content = read_file(TYPES_HEADER)
        for macro in categories.get("undeclared_macros", []):
            if macro not in KNOWN_MACROS and f"#define {macro}" not in types_content:
                val = self.deterministic_hash(macro)
                types_content += f"\n#ifndef {macro}\n  #define {macro} {val} /* AUTO-INJECTED */\n#endif"
                self.fixes_count += 1
        write_file(TYPES_HEADER, types_content)

        return self.fixes_count, self.modified_files

def apply_fixes(categories):
    engine = N64PatchEngine()
    return engine.run_cycle(categories)
