import os
import re
from collections import defaultdict
import logging

# Set up logging for the "Dynamic" process
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
        self.type_registry = set() # Track what we've defined dynamically

    def deterministic_hash(self, name):
        """Generates a unique but stable ID for macros/types."""
        h = 0
        for c in name: h = (31 * h + ord(c)) & 0xFFFFFFFF
        return (h % 80000) + 2000

    def ensure_base_types(self):
        """Ensures the foundation of the port is present and uncorrupted."""
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
            logging.info("Injected Core Primitive Layer.")

    def inject_missing_member(self, struct_name, member_name, context_hint=None):
        """
        DYNAMISM: Infers type based on 'context_hint' (the error line).
        """
        content = read_file(TYPES_HEADER)
        pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"
        
        # Heuristic Logic
        inferred_type = "long long int"
        if context_hint:
            if "->" in context_hint or "*" in context_hint: inferred_type = "void*"
            elif "." in context_hint: inferred_type = "struct unknown_s"
            elif any(x in member_name.lower() for x in ["id", "buf", "name", "data"]): 
                inferred_type = "u8[128]" # Likely an array

        def replacer(match):
            body = match.group(2)
            if member_name in body: return match.group(0)
            
            if "[" in inferred_type:
                base, size = inferred_type.split("[")
                decl = f"    {base} {member_name}[{size} /* AUTO-ARRAY */"
            else:
                decl = f"    {inferred_type} {member_name}; /* AUTO-INFERRED */"
                
            return f"{match.group(1)}{body}\n{decl}\n{match.group(3)}"

        if re.search(pattern, content):
            new_content = re.sub(pattern, replacer, content)
            write_file(TYPES_HEADER, new_content)
            self.fixes_count += 1

    def apply_surgical_fix(self, filepath, error_category, data):
        """Applies fixes only to specific lines or contexts to prevent corruption."""
        if not os.path.exists(filepath): return
        content = read_file(filepath)
        original = content

        if error_category == "expected_expression":
            # Fix: n64_memcpy(dest, {literal}, size) -> n64_memcpy(dest, (f32[]){literal}, size)
            content = re.sub(r'n64_memcpy\s*\(([^,]+),\s*\{([^}]+)\},\s*([^)]+)\)', 
                             r'n64_memcpy(\1, (f32[]){\2}, \3)', content)

        if error_category == "redefinition":
            # Comment out redefinitions instead of deleting (safety first)
            var_name = data
            content = re.sub(rf"^(.*?\b{re.escape(var_name)}\b.*?;)", r"/* AUTO-REDEF */ // \1", content, flags=re.MULTILINE)

        if content != original:
            write_file(filepath, content)
            self.modified_files.add(filepath)
            self.fixes_count += 1

    def run_cycle(self, categories):
        """The main execution loop for the Dynamic Recompiler."""
        self.ensure_base_types()

        # Handle Missing Members (The most complex dynamic part)
        for struct_name, member_name in categories.get("missing_members", []):
            self.inject_missing_member(struct_name, member_name)

        # Handle Surgical File Fixes
        for cat in ["expected_expression", "redefinition"]:
            for filepath, data in categories.get(cat, []):
                self.apply_surgical_fix(filepath, cat, data)

        # Handle Missing Types
        types_content = read_file(TYPES_HEADER)
        for filepath, tag in categories.get("missing_types", []):
            if tag in N64_STRUCT_BODIES:
                # Use the real SDK body if we have it
                if f"struct {tag}" not in types_content:
                    types_content += "\n" + N64_STRUCT_BODIES[tag]
                    self.fixes_count += 1
            else:
                # Generate a safe generic struct
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                if f"struct {struct_tag}" not in types_content:
                    types_content += f"\nstruct {struct_tag} {{ long long int pad[64]; }};\ntypedef struct {struct_tag} {tag};"
                    self.fixes_count += 1
            
            # Ensure file includes the type header
            if filepath and os.path.exists(filepath) and "n64_types.h" not in read_file(filepath):
                write_file(filepath, '#include "ultra/n64_types.h"\n' + read_file(filepath))

        # Handle Switch-Case Macro Conflicts
        for macro in categories.get("undeclared_macros", []):
            if macro not in KNOWN_MACROS and f"#define {macro}" not in types_content:
                val = self.deterministic_hash(macro)
                types_content += f"\n#ifndef {macro}\n  #define {macro} {val}\n#endif"
                self.fixes_count += 1

        write_file(TYPES_HEADER, types_content)
        return self.fixes_count, self.modified_files

# --- Entry Point ---
def apply_fixes(categories):
    engine = N64PatchEngine()
    return engine.run_cycle(categories)
