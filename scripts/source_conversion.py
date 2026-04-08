import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"

    def load_logic(self, level):
        """Loads rules for the current intelligence level."""
        self.rules = []
        pattern = os.path.join(self.logic_dir, f"source_logic_level{level}.txt")
        for logic_file in glob.glob(pattern):
            with open(logic_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Format: TYPE|NAME|SEARCH|REPLACEMENT
                        # TYPES: REGEX, HEADER_INJECT, STRUCT_BODY, MACRO
                        parts = line.split('|')
                        if len(parts) >= 4:
                            self.rules.append({
                                "action": parts[0],
                                "name": parts[1],
                                "search": parts[2],
                                "replace": parts[3].replace("\\n", "\n")
                            })

    def apply_to_file(self, file_path, error_context=""):
        """Determines which rules apply based on the error context."""
        if not os.path.exists(file_path): return 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        original_content = content
        changes = 0

        for rule in self.rules:
            if rule["action"] == "REGEX":
                if re.search(rule["search"], content):
                    content = re.sub(rule["search"], rule["replace"], content)
                    changes += 1
            
            elif rule["action"] == "HEADER_INJECT":
                if rule["search"] in error_context and rule["replace"] not in content:
                    content = f"{rule['replace']}\n{content}"
                    changes += 1

        if changes > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    🛠️  Applied {changes} fixes to {os.path.basename(file_path)}")
            
        return changes

    def bootstrap_n64_types(self):
        """Replicates the ensure_types_header_base logic."""
        if not os.path.exists(self.types_header):
            os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
            with open(self.types_header, 'w') as f:
                f.write("#pragma once\n#include <stdint.h>\n")
        
        # Additional logic to sync with source_logic_bootstrap.txt can go here
