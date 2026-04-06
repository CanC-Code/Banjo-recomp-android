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

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

class N64PatchEngine:
    def __init__(self):
        self.fixes_count = 0
        self.modified_files = set()
        # Basic N64 primitives that must NEVER be turned into auto-structs
        self.n64_primitives = {
            "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", 
            "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"
        }

    def is_patchable(self, filepath):
        if filepath == TYPES_HEADER: return True
        allowed_prefixes = ["src/", "include/"]
        return any(filepath.startswith(p) for p in allowed_prefixes)

    def ensure_base_types(self):
        """Forces primitives to the absolute top of the header."""
        primitives = """#ifndef CORE_PRIMITIVES_DEFINED
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
        
        # If the file is corrupted with auto-injected primitives, prune them
        for p_type in ["f32", "s32", "u32"]:
            content = re.sub(rf"typedef struct {p_type}_s {p_type};", "", content)
            content = re.sub(rf"struct {p_type}_s {{ .* }};", "", content)

        if "CORE_PRIMITIVES_DEFINED" not in content:
            # Strip existing pragma once to move it to the top
            clean_content = content.replace("#pragma once", "").strip()
            new_content = "#pragma once\n" + primitives + "\n" + clean_content
            write_file(TYPES_HEADER, new_content)
            logger.info(">>> Global Types Reset: Primitives moved to top.")

    def run_cycle(self, categories):
        self.ensure_base_types()
        if not categories: return 0, set()

        # 1. Surgical syntax fixes
        for cat in ["expected_expression", "redefinition"]:
            for filepath, data in categories.get(cat, []):
                if not os.path.exists(filepath) or not self.is_patchable(filepath): continue
                c = read_file(filepath)
                if cat == "expected_expression":
                    c = re.sub(r'n64_memcpy\s*\(([^,]+),\s*\{([^}]+)\},\s*([^)]+)\)', 
                               r'n64_memcpy(\1, (f32[]){\2}, \3)', c)
                elif cat == "redefinition":
                    c = re.sub(rf"^(.*?\b{re.escape(data)}\b.*?;)", r"/* AUTO-REDEF */ // \1", c, flags=re.MULTILINE)
                write_file(filepath, c)
                self.modified_files.add(filepath); self.fixes_count += 1

        # 2. SDK & Type Injection
        types_content = read_file(TYPES_HEADER)
        for filepath, tag in categories.get("missing_types", []):
            # DYNAMISM FIX: Skip if this is a known primitive
            if tag in self.n64_primitives:
                continue

            if tag in N64_STRUCT_BODIES and f"struct {tag}" not in types_content:
                types_content += "\n" + N64_STRUCT_BODIES[tag]
                self.fixes_count += 1
            else:
                s_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                if f"struct {s_tag}" not in types_content:
                    types_content += f"\nstruct {s_tag} {{ long long int pad[64]; }};\ntypedef struct {s_tag} {tag};"
                    self.fixes_count += 1
        
        write_file(TYPES_HEADER, types_content)
        return self.fixes_count, self.modified_files

def apply_fixes(categories):
    engine = N64PatchEngine()
    return engine.run_cycle(categories)
