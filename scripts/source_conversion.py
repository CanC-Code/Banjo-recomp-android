import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"
        # Track which global rules are already in the header to prevent "Layer Caking"
        self.applied_global_rules = set()

    def bootstrap_n64_types(self, clear_existing=False):
        """
        Ensures the global types header exists and has primitives at the very top.
        Call with clear_existing=True to wipe previous failed 'layers'.
        """
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
        
        if clear_existing and os.path.exists(self.types_header):
            os.remove(self.types_header)
            print("🧹 Cleared existing n64_types.h for a fresh sync.")

        content = ""
        if os.path.exists(self.types_header):
            with open(self.types_header, 'r', encoding='utf-8') as f:
                content = f.read()

        # Primitives wrapped in guards to prevent 'typedef redefinition' with SDK headers
        primitives = (
            "#ifndef N64_TYPES_PRIMITIVES_H\n"
            "#define N64_TYPES_PRIMITIVES_H\n"
            "#include <stdint.h>\n"
            "#ifndef _N64_PRIMS_DEFINED\n"
            "#define _N64_PRIMS_DEFINED\n"
            "typedef uint8_t u8; typedef int8_t s8;\n"
            "typedef uint16_t u16; typedef int16_t s16;\n"
            "typedef uint32_t u32; typedef int32_t s32;\n"
            "typedef uint64_t u64; typedef int64_t s64;\n"
            "typedef float f32; typedef double f64;\n"
            "typedef int32_t n64_bool;\n"
            "#endif\n"
            "#endif\n\n"
        )

        if "N64_TYPES_PRIMITIVES_H" not in content:
            with open(self.types_header, 'w', encoding='utf-8') as f:
                f.write(primitives + content)
            print("🚀 Bootstrapped N64 primitive types into n64_types.h")

    def load_logic(self):
        """Dynamically loads all rules from any file matching 'source_logic*.txt'."""
        self.rules = []
        pattern = os.path.join(self.logic_dir, "source_logic*.txt")
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
        print(f"--- Logic Loaded: {len(self.rules)} rules from {len(found_files)} files ---")

    def apply_to_file(self, file_path, error_context=""):
        """Applies loaded conversion rules to a specific file based on error context."""
        if not os.path.exists(file_path): return 0

        # The types header is the destination, we don't apply REGEX to it
        if "n64_types.h" in file_path:
            return 0

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        changes = 0
        original_content = content
        file_basename = os.path.basename(file_path).split('.')[0]

        for rule in self.rules:
            try:
                if rule["action"] == "REGEX":
                    new_content, count = re.subn(rule["search"], rule["replace"], content)
                    if count > 0:
                        content = new_content
                        changes += count
                
                elif rule["action"] == "HEADER_INJECT":
                    if re.search(rule["search"], error_context) and rule["replace"] not in content:
                        content = f"{rule['replace']}\n{content}"
                        changes += 1

                elif rule["action"] == "GLOBAL_INJECT":
                    # Logic fix: Only inject if this rule name isn't already active in the header
                    if re.search(rule["search"], error_context):
                        self._handle_global_inject(rule)
                        changes += 1

                elif rule["action"] == "STUB_INJECT":
                    match = re.search(rule["search"], error_context)
                    if match:
                        sym = match.group(1)
                        self._handle_stub_inject(sym)
                        changes += 1

            except re.error as e:
                print(f"    ⚠️ Regex Error in [{rule['name']}]: {e}")
                continue 

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    ✨ Fixed {changes} issue(s) in {os.path.basename(file_path)}")
        return changes

    def _handle_global_inject(self, rule):
        """Manages the generation of n64_types.h without creating duplicates."""
        types_content = ""
        if os.path.exists(self.types_header):
            with open(self.types_header, 'r') as tf: types_content = tf.read()

        # Check if the rule name or the content itself is already present
        rule_marker = f"/* Rule: {rule['name']} */"
        if rule_marker in types_content or rule["replace"].strip() in types_content:
            return

        with open(self.types_header, 'a') as tf:
            tf.write(f"\n{rule_marker}\n")
            tf.write(f"{rule['replace']}\n")
        print(f"    🧬 Injected {rule['name']} into n64_types.h")

    def _handle_stub_inject(self, sym):
        """Manages the generation of n64_stubs.c."""
        if not sym or sym.startswith("_Z") or "vtable" in sym:
            return

        stubs_content = ""
        if os.path.exists(self.stubs_file):
            with open(self.stubs_file, 'r') as sf: stubs_content = sf.read()
        
        stub_func = f"long long int {sym}() {{ return 0; }}"
        if stub_func not in stubs_content:
            with open(self.stubs_file, 'a') as sf:
                sf.write(f"{stub_func}\n")
            print(f"    🛠️ Stubbed missing symbol: {sym}")
