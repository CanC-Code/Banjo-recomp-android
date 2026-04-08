import os
import re
import glob

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        # Normalizing paths to ensure string comparisons work correctly
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"

    def bootstrap_n64_types(self):
        """Ensures the global types header exists and has primitives at the very top."""
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)

        content = ""
        if os.path.exists(self.types_header):
            with open(self.types_header, 'r', encoding='utf-8') as f:
                content = f.read()

        # Standard N64/Libultra primitive definitions. 
        # These are the foundations of the recompilation.
        primitives = (
            "#pragma once\n"
            "#include <stdint.h>\n"
            "typedef uint8_t u8;\n"
            "typedef int8_t s8;\n"
            "typedef uint16_t u16;\n"
            "typedef int16_t s16;\n"
            "typedef uint32_t u32;\n"
            "typedef int32_t s32;\n"
            "typedef uint64_t u64;\n"
            "typedef int64_t s64;\n"
            "typedef float f32;\n"
            "typedef double f64;\n"
            "typedef int32_t n64_bool;\n\n"
        )

        # Prepend primitives if f32 is missing to ensure system headers compile.
        # This is a critical safety net for headers like time.h or sched.h.
        if "typedef float f32;" not in content:
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

        # SAFETY: Protect the bootstrap header. 
        # If we run regex rules like 'f64' -> 'double' on n64_types.h, 
        # it creates 'typedef double double', which breaks the whole build.
        if "n64_types.h" in file_path:
            return 0

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        changes = 0
        original_content = content
        file_basename = os.path.basename(file_path).split('.')[0]

        for rule in self.rules:
            try:
                # REGEX: standard text replacement within the source file.
                # Used for primitive swapping and structural reformatting.
                if rule["action"] == "REGEX":
                    new_content, count = re.subn(rule["search"], rule["replace"], content)
                    if count > 0:
                        content = new_content
                        changes += count

                # HEADER_INJECT: Inserts an #include if a specific error is seen.
                elif rule["action"] == "HEADER_INJECT":
                    if re.search(rule["search"], error_context) and rule["replace"] not in content:
                        content = f"{rule['replace']}\n{content}"
                        changes += 1

                # POSIX_RENAME: Resolves name collisions (like 'round') by namespacing.
                elif rule["action"] == "POSIX_RENAME":
                    match = re.search(rule["search"], error_context)
                    if match:
                        func_name = match.group(1)
                        prefix = rule["replace"]
                        new_name = f"{prefix}_{file_basename}_{func_name}"
                        define = f"\n/* AUTO: fix static conflict */\n#define {func_name} {new_name}\n"
                        if define not in content:
                            includes = list(re.finditer(r'#include\s+.*?\n', content))
                            idx = includes[-1].end() if includes else 0
                            content = content[:idx] + define + content[idx:]
                            changes += 1

                # GLOBAL_INJECT: Writes structs/macros to the global n64_types.h.
                # This build the environment incrementally as types are discovered.
                elif rule["action"] == "GLOBAL_INJECT":
                    if re.search(rule["search"], error_context):
                        types_content = ""
                        if os.path.exists(self.types_header):
                            with open(self.types_header, 'r') as tf: types_content = tf.read()
                        if rule["replace"].strip() not in types_content:
                            with open(self.types_header, 'a') as tf:
                                tf.write(f"\n{rule['replace']}\n")
                            changes += 1

                # STUB_INJECT: Creates empty function stubs in n64_stubs.c.
                # Helps bypass missing link-time symbols during the iterative build.
                elif rule["action"] == "STUB_INJECT":
                    match = re.search(rule["search"], error_context)
                    if match:
                        sym = match.group(1)
                        # Avoid stubbing C++ mangled names or vtables
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
                print(f"    ⚠️ Regex Error in [{rule['name']}]: {e}")
                continue 

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    ✨ Fixed {changes} issue(s) in {os.path.basename(file_path)}")

        return changes
