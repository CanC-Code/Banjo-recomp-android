import os
import re
from collections import defaultdict
import logging

# Optimized logging to see exactly where the time is spent
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP")

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
        self.exclusion_zones = ["tools/", "emulator/", "lib/", "include/"]
        # Pre-compile regex for 10x speed boost
        self.re_memcpy = re.compile(r'n64_memcpy\s*\(([^,]+),\s*\{([^}]+)\},\s*([^)]+)\)')

    def is_patchable(self, filepath):
        return not any(zone in filepath for zone in self.exclusion_zones)

    def deterministic_hash(self, name):
        h = 0
        for c in name: h = (31 * h + ord(c)) & 0xFFFFFFFF
        return (h % 80000) + 5000 # Use a higher offset to avoid system IDs

    def ensure_base_types(self):
        """Standardizes the AArch64 foundation."""
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
            logger.info(">>> Port Foundation: Core Primitives Injected.")

    def fast_struct_patch(self, struct_name, member_name, context=""):
        """High-speed structural injection without recursive backtracking."""
        content = read_file(TYPES_HEADER)
        
        # Determine Type Heuristic
        t_type = "long long int"
        if "->" in context or "*" in context: t_type = "void*"
        elif "[" in context or any(x in member_name.lower() for x in ["id", "buf", "name", "data"]):
            t_type = "u8[256]"

        # Use a non-greedy find to locate the specific struct block
        pattern = rf"struct\s+{struct_name}\s*\{{([\s\S]*?)\}};"
        match = re.search(pattern, content)

        if match:
            body = match.group(1)
            if f" {member_name};" in body or f" {member_name}[" in body:
                # Type Promotion: Scalar -> Pointer/Array
                if t_type == "void*" and "long long int" in body:
                    new_body = body.replace(f"long long int {member_name};", f"void* {member_name}; /* PROMOTED */")
                    content = content.replace(body, new_body)
                    self.fixes_count += 1
            else:
                # Injection: Member is missing
                decl = f"    void* {member_name}; /* AUTO-PTR */" if t_type == "void*" else \
                       (f"    u8 {member_name}[256]; /* AUTO-ARR */" if "u8[" in t_type else f"    long long int {member_name};")
                new_body = body.rstrip() + f"\n{decl}\n"
                content = content.replace(body, new_body)
                self.fixes_count += 1
            
            write_file(TYPES_HEADER, content)

    def run_cycle(self, categories):
        self.ensure_base_types()
        
        if not categories:
            logger.warning("!!! Critical: No errors received from parser. Build is likely stuck.")
            return 0, set()

        # 1. Surgical syntax fixes
        for cat in ["expected_expression", "redefinition"]:
            for filepath, data in categories.get(cat, []):
                if not os.path.exists(filepath) or not self.is_patchable(filepath): continue
                c = read_file(filepath)
                if cat == "expected_expression":
                    c = self.re_memcpy.sub(r'n64_memcpy(\1, (f32[]){\2}, \3)', c)
                elif cat == "redefinition":
                    c = re.sub(rf"^(.*?\b{re.escape(data)}\b.*?;)", r"/* AUTO-REDEF */ // \1", c, flags=re.MULTILINE)
                
                if c != read_file(filepath):
                    write_file(filepath, c)
                    self.modified_files.add(filepath); self.fixes_count += 1

        # 2. Structural Fixes
        for struct_name, member_name in categories.get("missing_members", []):
            self.fast_struct_patch(struct_name, member_name, context=member_name)

        # 3. SDK & Type Injection
        types_content = read_file(TYPES_HEADER)
        for filepath, tag in categories.get("missing_types", []):
            if tag in N64_STRUCT_BODIES:
                if f"struct {tag}" not in types_content:
                    types_content += "\n" + N64_STRUCT_BODIES[tag]
                    self.fixes_count += 1
            elif tag not in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg", "RESAMPLE_STATE", "ENVMIX_STATE"]:
                s_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                if f"struct {s_tag}" not in types_content:
                    types_content += f"\nstruct {s_tag} {{ long long int pad[64]; }};\ntypedef struct {s_tag} {tag};"
                    self.fixes_count += 1
            
            if filepath and os.path.exists(filepath) and self.is_patchable(filepath):
                fc = read_file(filepath)
                if "n64_types.h" not in fc:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + fc)
                    self.modified_files.add(filepath); self.fixes_count += 1

        # 4. Macro ID Conflict Prevention
        for macro in categories.get("undeclared_macros", []):
            if macro not in KNOWN_MACROS and f"#define {macro}" not in types_content:
                val = self.deterministic_hash(macro)
                types_content += f"\n#ifndef {macro}\n  #define {macro} {val} /* DYNAMIC-ID */\n#endif"
                self.fixes_count += 1

        write_file(TYPES_HEADER, types_content)
        
        logger.info(f"Cycle Complete: Applied {self.fixes_count} fixes across {len(self.modified_files)} files.")
        return self.fixes_count, self.modified_files

def apply_fixes(categories):
    engine = N64PatchEngine()
    return engine.run_cycle(categories)
