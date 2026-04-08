import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"

    def load_logic(self, target_level):
        """Loads all rules cumulatively from Level 1 up to target_level."""
        self.rules = []
        # Loop through all levels from 1 to the current target
        for level in range(1, target_level + 1):
            pattern = os.path.join(self.logic_dir, f"source_logic_level{level}.txt")
            found_files = glob.glob(pattern)
            
            for logic_file in found_files:
                with open(logic_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split(':::')
                            if len(parts) >= 4:
                                self.rules.append({
                                    "action": parts[0],
                                    "name": parts[1],
                                    "search": parts[2],
                                    "replace": parts[3].replace("\\n", "\n")
                                })
        print(f"--- Logic Loaded: {len(self.rules)} rules active (Levels 1-{target_level}) ---")

    def apply_to_file(self, file_path, error_context=""):
        if not os.path.exists(file_path): return 0

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        changes = 0
        original_content = content
        file_basename = os.path.basename(file_path).split('.')[0]

        for rule in self.rules:
            try:
                # 1. Standard Regex Replacements
                if rule["action"] == "REGEX":
                    new_content, count = re.subn(rule["search"], rule["replace"], content)
                    if count > 0:
                        content = new_content
                        changes += count

                # 2. Local Header Injections
                elif rule["action"] == "HEADER_INJECT":
                    if re.search(rule["search"], error_context) and rule["replace"] not in content:
                        content = f"{rule['replace']}\n{content}"
                        changes += 1

                # 3. Dynamic POSIX Renaming (Uses the 'replacement' field as a prefix)
                elif rule["action"] == "POSIX_RENAME":
                    match = re.search(rule["search"], error_context)
                    if match:
                        func_name = match.group(1)
                        prefix = rule["replace"] # e.g., 'n64_renamed'
                        new_name = f"{prefix}_{file_basename}_{func_name}"
                        define = f"\n/* AUTO: fix static conflict */\n#define {func_name} {new_name}\n"
                        if define not in content:
                            # Insert after last include or at top
                            includes = list(re.finditer(r'#include\s+.*?\n', content))
                            idx = includes[-1].end() if includes else 0
                            content = content[:idx] + define + content[idx:]
                            changes += 1

                # 4. Global Type/Macro Injections
                elif rule["action"] == "GLOBAL_INJECT":
                    if re.search(rule["search"], error_context):
                        types_content = ""
                        if os.path.exists(self.types_header):
                            with open(self.types_header, 'r') as tf: types_content = tf.read()

                        if rule["replace"].strip() not in types_content:
                            with open(self.types_header, 'a') as tf:
                                tf.write(f"\n{rule['replace']}\n")
                            changes += 1

                # 5. Stubs Generation
                elif rule["action"] == "STUB_INJECT":
                    match = re.search(rule["search"], error_context)
                    if match:
                        sym = match.group(1)
                        if not sym.startswith("_Z") and "vtable" not in sym:
                            stubs_content = ""
                            if os.path.exists(self.stubs_file):
                                with open(self.stubs_file, 'r') as sf: stubs_content = sf.read()

                            stub_func = f"long long int {sym}() {{ return 0; }}"
                            if stub_func not in stubs_content:
                                with open(self.stubs_file, 'a') as sf:
                                    sf.write(f"{stub_func}\n")
                                changes += 1

            except re.error as e:
                print(f"    ⚠️ Regex Error in rule [{rule['name']}]: {e}")
                continue 

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    ✨ Fixed {changes} issue(s) in {os.path.basename(file_path)}")

        return changes

    def bootstrap_n64_types(self):
        """Ensures the global types header exists before compilation starts."""
        if not os.path.exists(self.types_header):
            os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
            with open(self.types_header, 'w') as f:
                f.write("#pragma once\n#include <stdint.h>\n")
                # ... standard typedefs ...
