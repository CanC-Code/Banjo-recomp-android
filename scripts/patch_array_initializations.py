import os
import re
import sys

# Supported types including custom N64 types
TYPES = r'\b(u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double|uint8_t|uint16_t|uint32_t)\b'
TARGET_DIRS = ["src", "include"]

def patch_arrays(root_path):
    print("🛠️ Starting Enhanced Array Initialization & Shadow Patch...")

    # Pattern 1: Assignment initialization: type name[size] = source;
    # Now supports variables for size (e.g., [tmp])
    assignment_pattern = re.compile(
        rf'^([ \t]+)({TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([a-zA-Z0-9_]+)\s*;',
        re.MULTILINE
    )

    # Pattern 2: Shadowed type variable: type type[size]; (e.g., u8 u8[tmp];)
    shadow_pattern = re.compile(
        rf'^([ \t]+)({TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;',
        re.MULTILINE
    )

    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue

        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not (filename.endswith('.c') or filename.endswith('.h')):
                    continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception: continue

                original_content = content

                # Fix 1: Resolve Shadowed Names (e.g., u8 u8[tmp] -> u8 buffer_u8[tmp])
                # We rename the variable to avoid it shadowing the type.
                content = shadow_pattern.sub(r'\1\2 buffer_\2[\4];', content)

                # Fix 2: Convert invalid array assignments to declarations + memcpy
                # Handles: u8 arr[6] = src; -> u8 arr[6]; memcpy(arr, src, 6 * sizeof(u8));
                def replace_assignment(match):
                    indent, type_name, var_name, size, src = match.groups()
                    # If shadowed rename was applied previously, ensure we use the new name
                    final_var = f"buffer_{var_name}" if type_name == var_name else var_name
                    return f"{indent}{type_name} {final_var}[{size}];\n{indent}memcpy({final_var}, {src}, {size} * sizeof({type_name}));"

                content = assignment_pattern.sub(replace_assignment, content)

                # Fix 3: Emergency 'tmp' declaration
                # If 'tmp' is used as an array size but not declared in the file
                if '[tmp]' in content and 'int tmp' not in content:
                    # Insert declaration after the last include
                    tmp_decl = "\n/* Emergency Decompiler Fix */\nstatic int tmp = 6;\n"
                    includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                    if includes:
                        pos = includes[-1].end()
                        content = content[:pos] + tmp_decl + content[pos:]
                    else:
                        content = tmp_decl + content

                if content != original_content:
                    # Ensure <string.h> is present for memcpy
                    if 'memcpy' in content and '<string.h>' not in content:
                        if '#include' in content:
                            content = re.sub(r'(#include\s+<.*?>|#include\s+".*?")', r'#include <string.h>\n\1', content, count=1)
                        else:
                            content = "#include <string.h>\n" + content

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Fixed Array/Shadow/Tmp] {filepath}")

    print(f"✅ Patch complete! Modified {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_arrays(root_dir)
