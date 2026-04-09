import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"

    def repair_unterminated_conditionals(self, content: str) -> str:
        lines = content.split('\n')
        stack = []
        remove = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'#\s*(?:ifndef|ifdef|if)\b', stripped):
                stack.append(i)
            elif re.match(r'#\s*endif\b', stripped):
                if stack:
                    stack.pop()
        for idx in stack:
            remove.add(idx)
            for j in range(idx + 1, min(idx + 4, len(lines))):
                if lines[j].strip().startswith('#define'):
                    remove.add(j)
                    break
        if not remove: return content
        print(f"    🩹 Repaired {len(remove)} unterminated preprocessor conditionals.")
        return '\n'.join([line for i, line in enumerate(lines) if i not in remove])

    def bootstrap_n64_types(self, clear_existing=False):
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
        if clear_existing and os.path.exists(self.types_header):
            os.remove(self.types_header)
            print("🧹 Cleared existing n64_types.h for a fresh sync.")
        if not os.path.exists(self.types_header):
            with open(self.types_header, 'w', encoding='utf-8') as f:
                f.write("#pragma once\n\n/* N64 Recompilation Bridge Header */\n")
            print("🚀 Initialized fresh n64_types.h")

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
                                "action": parts[0], "name": parts[1],
                                "search": parts[2], "replace": parts[3].replace("\\n", "\n")
                            })
        print(f"--- Logic Loaded: {len(self.rules)} rules ---")

    def apply_to_file(self, file_path, error_context=""):
        # THE FIX: Removed the logic blocking n64_types.h
        if not os.path.exists(file_path): return 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        changes, original_content = 0, content
        
        for rule in self.rules:
            try:
                if rule["action"] == "REGEX":
                    new_content, count = re.subn(rule["search"], rule["replace"], content)
                    if count > 0: content, changes = new_content, changes + count
                
                elif rule["action"] == "HEADER_INJECT":
                    if re.search(rule["search"], error_context) and rule["replace"] not in content:
                        content, changes = f"{rule['replace']}\n{content}", changes + 1
                
                elif rule["action"] == "GLOBAL_INJECT":
                    # THE FIX: Execute ONLY if explicitly routed to n64_types.h
                    if "n64_types.h" in file_path and re.search(rule["search"], error_context):
                        rule_marker = f"/* Rule: {rule['name']} */"
                        if rule_marker not in content:
                            new_header_data = f"{content}\n{rule_marker}\n{rule['replace']}\n"
                            content = self.repair_unterminated_conditionals(new_header_data)
                            changes += 1 # Only increment if an actual injection occurred!
                            print(f"    🧬 Injected {rule['name']} into n64_types.h")
                            
                elif rule["action"] == "STUB_INJECT":
                    match = re.search(rule["search"], error_context)
                    if match:
                        if self._handle_stub_inject(match.group(1)):
                            changes += 1
            except re.error: continue 
                
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
        return changes

    def _handle_stub_inject(self, sym):
        if not sym or sym.startswith("_Z") or "vtable" in sym: return False
        stubs_content = ""
        if os.path.exists(self.stubs_file):
            with open(self.stubs_file, 'r', encoding='utf-8') as sf: stubs_content = sf.read()
        stub_func = f"long long int {sym}() {{ return 0; }}"
        if stub_func not in stubs_content:
            with open(self.stubs_file, 'a', encoding='utf-8') as sf: sf.write(f"{stub_func}\n")
            print(f"    🛠️ Stubbed missing symbol: {sym}")
            return True
        return False
