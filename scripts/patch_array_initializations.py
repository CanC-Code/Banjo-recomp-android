import os
import re
import sys

TYPES = r'\b(u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double|uint8_t|uint16_t|uint32_t)\b'
TARGET_DIRS = ["src", "include"]

def patch_arrays(root_path):
    print("🛠️ Starting Advanced Array Initialization & Usage Patch...")

    # Pattern 1: Assignment initialization: type name[size] = source;
    assignment_pattern = re.compile(
        rf'^([ \t]+)({TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([a-zA-Z0-9_]+)\s*;',
        re.MULTILINE
    )

    # Pattern 2: Shadowed type variable: type type[size];
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

                # Fix 1: Resolve Shadowed Names AND Usages
                # We find 'u8 u8[' and replace all subsequent standalone 'u8' tokens with 'buffer_u8'
                shadow_matches = shadow_pattern.findall(content)
                for indent, type_name, var_name, size in shadow_matches:
                    # Rename the declaration
                    decl_pattern = rf'{indent}{type_name}\s+{var_name}\s*\['
                    content = re.sub(decl_pattern, f'{indent}{type_name} buffer_{var_name}[', content)
                    
                    # Rename all standalone usages of this variable in the file
                    # Uses negative lookahead/behind to ensure we aren't hitting the type declaration
                    usage_pattern = rf'(?<!{type_name}\s)\b{var_name}\b(?!\s*\[)'
                    content = re.sub(usage_pattern, f'buffer_{var_name}', content)

                # Fix 2: Convert invalid assignments
                def replace_assignment(match):
                    indent, type_name, var_name, size, src = match.groups()
                    final_var = f"buffer_{var_name}" if type_name == var_name else var_name
                    return f"{indent}{type_name} {final_var}[{size}];\n{indent}memcpy({final_var}, {src}, {size} * sizeof({type_name}));"

                content = assignment_pattern.sub(replace_assignment, content)

                # Fix 3: Emergency 'tmp' array declaration
                # Since the log shows 'tmp' being indexed (tmp[index]), it must be an array/pointer.
                if '[tmp]' in content or 'tmp[' in content:
                    if 'int tmp' not in content and 'u8 tmp' not in content:
                        tmp_decl = "\n/* Emergency Decompiler Fix: tmp is used as an array */\nstatic u8 tmp[1024] = {0};\n"
                        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                        if includes:
                            pos = includes[-1].end()
                            content = content[:pos] + tmp_decl + content[pos:]
                        else:
                            content = tmp_decl + content

                if content != original_content:
                    if 'memcpy' in content and '<string.h>' not in content:
                        if '#include' in content:
                            content = re.sub(r'(#include\s+<.*?>|#include\s+".*?")', r'#include <string.h>\n\1', content, count=1)
                        else:
                            content = "#include <string.h>\n" + content

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Fixed Array & Usages] {filepath}")

    print(f"✅ Patch complete! Modified {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_arrays(root_dir)
