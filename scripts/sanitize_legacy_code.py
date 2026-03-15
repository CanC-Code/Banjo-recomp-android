import os
import re
import sys

# Directories to process within the root path
TARGET_DIRS = ["src", "include"]

# Symbols to namespace to avoid collisions
TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "TRUE",
    r"\bfalse\b": "FALSE",
    r"\bstrcat\b": "n64_strcat",
    r"\bstrcpy\b": "n64_strcpy",
    r"\bstrlen\b": "n64_strlen",
    r"\bmemcpy\b": "n64_memcpy",
    r"\bmemmove\b": "n64_memmove",
    r"\bmalloc\b": "n64_malloc",
    r"\bfree\b": "n64_free",
    r"\brealloc\b": "n64_realloc",
    r"\bcalloc\b": "n64_calloc",
    r"\bsprintf\b": "n64_sprintf",
    r"\bprintf\b": "n64_printf",
    r"\bsin\b": "n64_sin",
    r"\bcos\b": "n64_cos",
}

# Types that often shadow variables in decompiled code (using non-capturing ?: group)
SHADOW_TYPES = r'\b(?:u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double)\b'

def fix_decompiler_artifacts(content, filename):
    """
    Handles broken code patterns like 'u8 u8[tmp]' or 'u8 arr[6] = src'.
    """
    # 1. Fix Shadowed Names AND Usages Safely
    shadow_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;', re.MULTILINE)
    shadow_matches = shadow_pattern.findall(content)

    for indent, type_name, var_name, size in shadow_matches:
        decl_line = rf'{indent}{type_name}\s+{var_name}\s*\['
        content = re.sub(decl_line, f'{indent}{type_name} buffer_{var_name}[', content)
        
        # Rename safe array index usages
        content = re.sub(rf'\b{var_name}\s*\[', f'buffer_{var_name}[', content)
        # Rename in memory function targets
        content = re.sub(rf'\b(memcpy|memset|memmove)\s*\(\s*{var_name}\s*,', rf'\1(buffer_{var_name},', content)

    # 2. Fix Invalid Array Assignments
    assign_pattern = re.compile(
        rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([a-zA-Z0-9_]+)\s*;',
        re.MULTILINE
    )

    def array_to_memcpy(match):
        indent, dtype, name, size, src = match.groups()
        final_name = f"buffer_{name}" if dtype == name else name
        return f"{indent}{dtype} {final_name}[{size}];\n{indent}memcpy({final_name}, {src}, {size} * sizeof({dtype}));"

    content = assign_pattern.sub(array_to_memcpy, content)

    # 3. Emergency 'tmp' array declaration for leafboat.c style errors
    if ('[tmp]' in content or 'tmp[' in content) and 'int tmp' not in content and 'u8 tmp' not in content:
        tmp_decl = "\n/* Emergency Decompiler Fix */\nstatic u8 tmp[1024] = {0};\n"
        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
        if includes:
            pos = includes[-1].end()
            content = content[:pos] + tmp_decl + content[pos:]
        else:
            content = tmp_decl + content

    # 4. Math Constant Protection (M_PI)
    if 'M_PI' in content and 'math.h' in content and '#define M_PI' not in content:
        pi_fix = "\n#ifndef M_PI\n#define M_PI 3.14159265358979323846\n#endif\n"
        content = re.sub(r'^(#include <math\.h>)$', r'\1' + pi_fix, content, flags=re.MULTILINE)

    return content

def fix_linkage_conflicts(content):
    static_func_pattern = re.compile(r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\)\s*)\{", re.MULTILINE)
    matches = static_func_pattern.findall(content)
    if not matches: return content

    signatures = []
    existing_decls = set(re.findall(r"^static\s+.*?;", content, re.MULTILINE))
    for full_sig, func_name in matches:
        decl = f"{full_sig.strip()};"
        if decl not in existing_decls:
            signatures.append(decl)
            existing_decls.add(decl)

    for _, func_name in matches:
        mismatch_pattern = rf"^(?!\s)(?<!static\s)([\w\s\*]*?\b{func_name}\b\s*\([^)]*\)\s*;)"
        content = re.sub(mismatch_pattern, r"static \1", content, flags=re.MULTILINE)

    if signatures:
        header_block = "\n/* Automated Forward Decls */\n" + "\n".join(signatures) + "\n"
        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
        if includes:
            pos = includes[-1].end()
            content = content[:pos] + "\n" + header_block + content[pos:]
        else:
            content = header_block + "\n" + content
    return content

def sanitize_codebase(root_path):
    print(f"🧹 Scanning for sanitization: {root_path}")
    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h', '.cpp')): continue
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                except Exception: continue

                original_content = "".join(lines)
                new_lines = []
                for line in lines:
                    if line.strip().startswith("#include"):
                        new_lines.append(line)
                        continue
                    for pattern, replacement in TOKEN_REPLACEMENTS.items():
                        line = re.sub(pattern, replacement, line)
                    new_lines.append(line)

                content = "".join(new_lines)
                content = fix_decompiler_artifacts(content, filename)
                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Sanitized] {filepath}")
    print(f"✅ Sanitization Complete! {patch_count} files modified.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
