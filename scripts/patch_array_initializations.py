import os
import re
import sys

# Supported types (using non-capturing ?: group to prevent unpacking errors)
TYPES = r'\b(?:u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double|uint8_t|uint16_t|uint32_t)\b'
TARGET_DIRS = ["src", "include"]

def patch_arrays(root_path):
    print("🛠️ Starting Advanced Array Initialization & Usage Patch...")

    # Matches illegal C array assignment: u8 arr[size] = src;
    assignment_pattern = re.compile(
        rf'^([ \t]+)({TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([a-zA-Z0-9_]+)\s*;',
        re.MULTILINE
    )

    # Matches variables named after their own type: u8 u8[size];
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
                # 🛡️ Only touch C/H files. Skip CPP emulator code and core N64 types header.
                if not filename.endswith(('.c', '.h')): continue
                if filename == "n64_types.h": continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception: continue

                original_content = content

                # 1. Fix Shadowed Names AND Usages Safely
                shadow_matches = shadow_pattern.findall(content)
                for indent, type_name, var_name, size in shadow_matches:
                    decl_pattern = rf'{indent}{type_name}\s+{var_name}\s*\['
                    content = re.sub(decl_pattern, f'{indent}{type_name} buffer_{var_name}[', content)
                    
                    # FIX: Uses negative lookahead `(?!\s*\])` so we don't accidentally ruin function params like `void func(u8 [])`
                    content = re.sub(rf'\b{var_name}\s*\[(?!\s*\])', f'buffer_{var_name}[', content)
                    content = re.sub(rf'\b(memcpy|memset|memmove)\s*\(\s*{var_name}\s*,', rf'\1(buffer_{var_name},', content)

                # 2. Fix Invalid Assignments (Converts to local array + memcpy)
                def replace_assignment(match):
                    indent, dtype, name, size, src = match.groups()
                    final_name = f"buffer_{name}" if dtype == name else name
                    return f"{indent}{dtype} {final_name}[{size}];\n{indent}memcpy({final_name}, {src}, {size} * sizeof({dtype}));"

                content = assignment_pattern.sub(replace_assignment, content)

                # 3. Emergency 'tmp' array declaration
                # FIX: Uses Regex to ensure 'tmp' isn't legally declared as ANY type (f32, s16, struct X, etc.)
                is_tmp_used = '[tmp]' in content or 'tmp[' in content
                is_tmp_declared = bool(re.search(r'\b\w+\s+\**tmp\b\s*(?:\[|;|=)', content))
                
                if is_tmp_used and not is_tmp_declared:
                    tmp_decl = "\n/* Emergency Decompiler Fix: tmp used as array */\nstatic u8 tmp[1024] = {0};\n"
                    includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                    if includes:
                        pos = includes[-1].end()
                        content = content[:pos] + tmp_decl + content[pos:]
                    else:
                        content = tmp_decl + content

                # 4. Safe String.h Injection
                if content != original_content:
                    if 'memcpy' in content and '<string.h>' not in content:
                        # FIX: Inject after existing includes so we don't violate Header Guards
                        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                        if includes:
                            pos = includes[-1].end()
                            content = content[:pos] + "\n#include <string.h>\n" + content[pos:]
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
