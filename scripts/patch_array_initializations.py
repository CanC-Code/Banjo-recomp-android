import os
import re
import sys

# Supported types including common C primitives and custom typedefs
TYPES = r'\b(u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double|uint8_t|uint16_t|uint32_t)\b'
TARGET_DIRS = ["src", "include"]

def patch_arrays(root_path):
    print("🛠️ Starting Enhanced Array Initialization Patch...")

    # Regex breakdown:
    # 1. Matches type, name, and size.
    # 2. Ensures there is an assignment '=' to another identifier.
    # 3. Specifically looks for assignments that aren't string literals or brace initializers.
    pattern = re.compile(
        rf'({TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*(\d+)\s*\]\s*=\s*([a-zA-Z0-9_]+)\s*;',
        re.MULTILINE
    )

    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path):
            continue

        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not (filename.endswith('.c') or filename.endswith('.h')):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception:
                    continue

                original_content = content

                # Perform the replacement: Type Name[Size]; memcpy(Name, Source, Size * sizeof(Type));
                replacement = r'\1 \2[\3];\n    memcpy(\2, \4, \3 * sizeof(\1));'
                
                # Check for global scope: We only patch if the line is indented (likely inside a function)
                # To be safer, we only replace lines that start with at least one space or tab.
                content = re.sub(rf'^[ \t]+{pattern.pattern}', replacement, content, flags=re.MULTILINE)

                if content != original_content:
                    # 🛡️ Safety: Ensure <string.h> exists for memcpy
                    if 'memcpy' in content and '<string.h>' not in content:
                        if '#include' in content:
                            content = re.sub(r'(#include\s+<.*?>|#include\s+".*?")', r'#include <string.h>\n\1', content, count=1)
                        else:
                            content = "#include <string.h>\n" + content

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Fixed Array & Header] {filepath}")

    print(f"✅ Patch complete! Modified {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_arrays(root_dir)
