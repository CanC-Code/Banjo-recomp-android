import os
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP")

from error_parser import (
    N64_STRUCT_BODIES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

class N64PatchEngine:
    def __init__(self):
        self.fixes_count = 0
        self.modified_files = set()
        self.n64_primitives = {
            "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", 
            "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"
        }

    def is_patchable(self, filepath):
        return filepath == TYPES_HEADER or filepath.startswith(("src/", "include/"))

    def fix_header_order(self):
        """Forces primitives to the top and moves includes below them."""
        if not os.path.exists(TYPES_HEADER): return
        
        content = read_file(TYPES_HEADER)
        
        # 1. Clean out any previous "broken" auto-structs for primitives
        for p in ["f32", "s32", "u32", "u16", "s16", "u8"]:
            content = re.sub(rf"typedef struct {p}_s {p};", "", content)
            content = re.sub(rf"struct {p}_s {{.*?}};", "", content, flags=re.DOTALL)

        # 2. Extract all #include lines
        includes = re.findall(r'^#include.*$', content, re.MULTILINE)
        # Remove them from the main body
        clean_body = re.sub(r'^#include.*$', '', content, flags=re.MULTILINE)
        # Prune existing pragma once to re-add it at the very top
        clean_body = clean_body.replace("#pragma once", "").strip()

        primitives = """#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
#include <stdint.h>
typedef uint8_t u8;   typedef int8_t s8;
typedef uint16_t u16; typedef int16_t s16;
typedef uint32_t u32; typedef int32_t s32;
typedef uint64_t u64; typedef int64_t s64;
typedef float f32;    typedef double f64;
typedef int n64_bool;
typedef u32 OSIntMask; typedef u64 OSTime;
typedef u32 OSId;      typedef s32 OSPri;
typedef void* OSMesg;
#endif"""

        # 3. Reconstruct: Pragma -> Primitives -> Includes -> Structs
        new_header = "#pragma once\n" + primitives + "\n\n"
        new_header += "\n".join(includes) + "\n\n"
        new_header += clean_body
        
        write_file(TYPES_HEADER, new_header)
        logger.info(">>> Surgical Header Repair: Moved primitives above includes in n64_types.h")

    def run_cycle(self, categories):
        self.fix_header_order()
        if not categories: return 0, set()

        # Handle missing types, but ignore primitives (handled by fix_header_order)
        types_content = read_file(TYPES_HEADER)
        for filepath, tag in categories.get("missing_types", []):
            if tag in self.n64_primitives: continue
            
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
