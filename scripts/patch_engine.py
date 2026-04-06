import os
import re
import logging
from collections import defaultdict

# Faster logging for Github Actions
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP")

from error_parser import (
    N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

class N64PatchEngine:
    def __init__(self):
        self.fixes_count = 0
        self.modified_files = set()
        # Only exclude core emulator logic and standard library includes
        self.protected_zones = ["emulator/", "lib/", "include/PR/"]

    def deterministic_hash(self, name):
        """Stable unique IDs for macros to prevent switch-case duplicate value errors."""
        h = 0
        for c in name: h = (31 * h + ord(c)) & 0xFFFFFFFF
        return (h % 80000) + 5000

    def infer_type(self, member_name, context_line):
        """DYNAMISM: Infer C type based on code usage."""
        if "->" in context_line or "*" in context_line or "ptr" in member_name.lower():
            return "void*"
        if "[" in context_line or any(x in member_name.lower() for x in ["id", "buf", "data"]):
            return "u8[256]"
        return "long long int"

    def fast_patch_struct(self, struct_name, member_name, context=""):
        """Injected members now respect the inferred type from the error context."""
        content = read_file(TYPES_HEADER)
        target_type = self.infer_type(member_name, context)
        
        # Use non-greedy match to find the specific struct block quickly
        pattern = rf"struct\s+{struct_name}\s*\{{([\s\S]*?)\}};"
        match = re.search(pattern, content)

        if match:
            body = match.group(1)
            if f" {member_name};" not in body and f" {member_name}[" not in body:
                decl = f"    {target_type} {member_name}; /* AUTO-INFERRED */"
                new_body = body.rstrip() + f"\n{decl}\n"
                content = content.replace(body, new_body)
                write_file(TYPES_HEADER, content)
                self.fixes_count += 1
                logger.info(f"Dynamically added {struct_name}.{member_name} as {target_type}")

    def run_cycle(self, categories):
        if not categories:
            logger.error("!!! Build stalled: Parser found 0 errors. Check error_parser.py regex.")
            return 0, set()

        # 1. Structural Fixes (The primary dynamic driver)
        for struct_name, member_name in categories.get("missing_members", []):
            # We pass the member name as the initial context if the log line isn't available
            self.fast_patch_struct(struct_name, member_name, context=member_name)

        # 2. Global Type Promotion
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
        
        # 3. Macro Collision Prevention
        for macro in categories.get("undeclared_macros", []):
            if macro not in KNOWN_MACROS and f"#define {macro}" not in types_content:
                val = self.deterministic_hash(macro)
                types_content += f"\n#ifndef {macro}\n  #define {macro} {val} /* DYNAMIC-ID */\n#endif"
                self.fixes_count += 1

        write_file(TYPES_HEADER, types_content)
        logger.info(f"Cycle Result: {self.fixes_count} dynamic patches applied.")
        return self.fixes_count, self.modified_files

def apply_fixes(categories):
    engine = N64PatchEngine()
    return engine.run_cycle(categories)
