import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"
        self.applied_global_rules = set()

    def repair_unterminated_conditionals(self, content: str) -> str:
        """
        Scans for unclosed #if/#ifndef blocks and removes orphaned guards.
        Ensures the generated n64_types.h is always syntactically valid.
        """
        lines = content.split('\n')
        stack = []  # Tracks line indices of opening directives
        remove = set()

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match #if, #ifdef, #ifndef
            if re.match(r'#\s*(?:ifndef|ifdef|if)\b', stripped):
                stack.append(i)
            elif re.match(r'#\s*endif\b', stripped):
                if stack:
                    stack.pop()
        
        # Any remaining indices in stack are unclosed guards
        for idx in stack:
            remove.add(idx)
            # Aggressively remove the #define usually associated with an #ifndef on next lines
            for j in range(idx + 1, min(idx + 4, len(lines))):
                if lines[j].strip().startswith('#define'):
                    remove.add(j)
                    break

        if not remove:
            return content
            
        print(f"    🩹 Repaired {len(remove)} unterminated preprocessor conditionals.")
        return '\n'.join([line for i, line in enumerate(lines) if i not in remove])

    def bootstrap_n64_types(self, clear_existing=False):
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
        if clear_existing and os.path.exists(self.types_header):
            os.remove(self.types_header)
            print("🧹 Cleared existing n64_types.h for a fresh sync.")

        content = ""
        if os.path.exists(self.types_header):
            with open(self.types_header, 'r', encoding='utf-8') as f:
                content = f.read()

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

    def _handle_global_inject(self, rule):
        types_content = ""
        if os.path.exists(self.types_header):
            with open(self.types_header, 'r', encoding='utf-8') as tf: 
                types_content = tf.read()

        rule_marker = f"/* Rule: {rule['name']} */"
        if rule_marker in types_content or rule["replace"].strip() in types_content:
            return

        # Append new rule content
        new_header_data = f"{types_content}\n{rule_marker}\n{rule['replace']}\n"
        
        # Apply the preprocessor repair logic
        repaired_content = self.repair_unterminated_conditionals(new_header_data)

        with open(self.types_header, 'w', encoding='utf-8') as tf:
            tf.write(repaired_content)
        print(f"    🧬 Injected {rule['name']} into n64_types.h")

    def apply_to_file(self, file_path, error_context=""):
        if not os.path.exists(file_path): return 0
        if "n64_types.h" in file_path: return 0
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        changes = 0
        original_content = content
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
                continue 
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        return changes

    def _handle_stub_inject(self, sym):
        if not sym or sym.startswith("_Z") or "vtable" in sym: return
        stubs_content = ""
        if os.path.exists(self.stubs_file):
            with open(self.stubs_file, 'r', encoding='utf-8') as sf: 
                stubs_content = sf.read()
        stub_func = f"long long int {sym}() {{ return 0; }}"
        if stub_func not in stubs_content:
            with open(self.stubs_file, 'a', encoding='utf-8') as sf:
                sf.write(f"{stub_func}\n")
            print(f"    🛠️ Stubbed missing symbol: {sym}")
