import os
import re
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP")

from error_parser import (
    N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, read_file, write_file
)

# The only Android-side file we are allowed to touch (our types database)
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

class N64PatchEngine:
    def __init__(self):
        self.fixes_count = 0
        self.modified_files = set()

    def is_patchable(self, filepath):
        """
        STRICT MODE: Only allows patching the game source, headers, 
        or the internal types header. Blocks all other Android/ folder files.
        """
        # Always allow our central types header
        if filepath == TYPES_HEADER:
            return True
        
        # Only allow game-specific source and includes
        allowed_prefixes = ["src/", "include/"]
        return any(filepath.startswith(p) for p in allowed_prefixes)

    def deterministic_hash(self, name):
        h = 0
        for c in name: h = (31 * h + ord(c)) & 0xFFFFFFFF
        return (h % 80000) + 5000

    def ensure_base_types(self):
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
            logger.info(">>> Global Types initialized in ultra/n64_types.h")

    def infer_and_patch_member(self, struct_name, member_name, context_line=""):
        content = read_file(TYPES_HEADER)
        t_type = "long long int"
        if "->" in context_line or "*" in context_line: 
            t_type = "void*"
        elif "[" in context_line or any(x in member_name.lower() for x in ["id", "buf", "name", "data"]):
            t_type = "u8[256]"

        pattern = rf"(struct\s+{struct_name}\s*\{{)([\s\S]*?)(\}});"
        match = re.search(pattern, content)
        
        if match:
            header, body, footer = match.group(1), match.group(2), match.group(3)
            if f" {member_name};" not in body and f" {member_name}[" not in body:
                decl = f"    {t_type} {member_name}; /* AUTO-INFERRED */"
                body = body.rstrip() + f"\n{decl}\n"
                new_content = content[:match.start()] + header + body + footer + content[match.end():]
                write_file(TYPES_HEADER, new_content)
                self.fixes_count += 1

    def run_cycle(self, categories):
        self.ensure_base_types()
        if not categories: return 0, set()

        # 1. Surgical syntax fixes (STRICTLY SOURCE ONLY)
        for cat in ["expected_expression", "redefinition"]:
            for filepath, data in categories.get(cat, []):
                if not os.path.exists(filepath) or not self.is_patchable(filepath):
                    continue
                
                c = read_file(filepath)
                if cat == "expected_expression":
                    c = re.sub(r'n64_memcpy\s*\(([^,]+),\s*\{([^}]+)\},\s*([^)]+)\)', 
                               r'n64_memcpy(\1, (f32[]){\2}, \3)', c)
                elif cat == "redefinition":
                    c = re.sub(rf"^(.*?\b{re.escape(data)}\b.*?;)", r"/* AUTO-REDEF */ // \1", c, flags=re.MULTILINE)
                
                if c != read_file(filepath):
                    write_file(filepath, c)
                    self.modified_files.add(filepath); self.fixes_count += 1

        # 2. Dynamic Structural Fixes (Always directed to TYPES_HEADER)
        for struct_name, member_name in categories.get("missing_members", []):
            self.infer_and_patch_member(struct_name, member_name, context_line=member_name)

        # 3. SDK & Type Injection (Always directed to TYPES_HEADER)
        types_content = read_file(TYPES_HEADER)
        for filepath, tag in categories.get("missing_types", []):
            if tag in N64_STRUCT_BODIES and f"struct {tag}" not in types_content:
                types_content += "\n" + N64_STRUCT_BODIES[tag]
                self.fixes_count += 1
            elif tag not in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
                s_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                if f"struct {s_tag}" not in types_content:
                    types_content += f"\nstruct {s_tag} {{ long long int pad[64]; }};\ntypedef struct {s_tag} {tag};"
                    self.fixes_count += 1
            
            # Auto-include the types header if a source file needs it
            if filepath and os.path.exists(filepath) and self.is_patchable(filepath):
                fc = read_file(filepath)
                if "n64_types.h" not in fc:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + fc)
                    self.modified_files.add(filepath); self.fixes_count += 1

        # 4. Macro ID Conflict Prevention (Always directed to TYPES_HEADER)
        for macro in categories.get("undeclared_macros", []):
            if macro not in KNOWN_MACROS and f"#define {macro}" not in types_content:
                val = self.deterministic_hash(macro)
                types_content += f"\n#ifndef {macro}\n  #define {macro} {val} /* DYNAMIC-ID */\n#endif"
                self.fixes_count += 1

        write_file(TYPES_HEADER, types_content)
        logger.info(f"Source Patching Cycle Complete: {self.fixes_count} updates.")
        return self.fixes_count, self.modified_files

def apply_fixes(categories):
    engine = N64PatchEngine()
    return engine.run_cycle(categories)
