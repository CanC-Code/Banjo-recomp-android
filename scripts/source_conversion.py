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
            with open(logic_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split('|')
                        if len(parts) >= 4:
                            self.rules.append({
                                "action": parts[0],
                                "name": parts[1],
                                "search": parts[2],
                                "replace": parts[3].replace("\\n", "\n")
                            })

    def apply_to_file(self, file_path, error_context=""):
        if not os.path.exists(file_path): return 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        changes = 0
        original_content = content
        file_basename = os.path.basename(file_path).split('.')[0]

        for rule in self.rules:
            # 1. Standard Regex Replacements in the Source File
            if rule["action"] == "REGEX":
                if re.search(rule["search"], content):
                    content = re.sub(rule["search"], rule["replace"], content)
                    changes += 1

            # 2. Local Header Injections
            elif rule["action"] == "HEADER_INJECT":
                if re.search(rule["search"], error_context) and rule["replace"] not in content:
                    content = f"{rule['replace']}\n{content}"
                    changes += 1

            # 3. Dynamic POSIX Renaming (e.g. read() -> n64_filename_read())
            elif rule["action"] == "POSIX_RENAME":
                if re.search(rule["search"], error_context):
                    # Find exactly which function caused the static conflict
                    match = re.search(rule["search"], error_context)
                    if match:
                        func_name = match.group(1)
                        new_name = f"n64_{file_basename}_{func_name}"
                        define = f"\n/* AUTO: fix static conflict */\n#define {func_name} {new_name}\n"
                        if define not in content:
                            # Inject right after includes
                            includes = list(re.finditer(r'#include\s+.*?\n', content))
                            idx = includes[-1].end() if includes else 0
                            content = content[:idx] + define + content[idx:]
                            changes += 1

            # 4. Global Type/Macro Injections (Targeting n64_types.h)
            elif rule["action"] == "GLOBAL_INJECT":
                if re.search(rule["search"], error_context):
                    types_content = ""
                    if os.path.exists(self.types_header):
                        with open(self.types_header, 'r') as tf: types_content = tf.read()
                    
                    if rule["replace"].strip() not in types_content:
                        with open(self.types_header, 'a') as tf:
                            tf.write(f"\n{rule['replace']}\n")
                        changes += 1

            # 5. Stubs Generation (Targeting n64_stubs.c)
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

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    ✨ Fixed {changes} issue(s) in {os.path.basename(file_path)}")
            
        return changes
