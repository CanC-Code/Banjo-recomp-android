import os
import re
import sys

TARGET_DIRS = ["src", "include"]

# SAFE replacements only (no libc hijacking unless guaranteed implemented)
TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "TRUE",
    r"\bfalse\b": "FALSE",
}

COMPILED_TOKENS = [(re.compile(k), v) for k, v in TOKEN_REPLACEMENTS.items()]

SHADOW_TYPES = r'\b(?:u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double)\b'


def safe_token_replacement(content):
    """
    Safely replaces tokens in C/C++ code while ignoring strings and comments.
    """
    pattern = re.compile(
        r'(?P<string>"(?:\\.|[^"\\])*")|'
        r"(?P<char>'(?:\\.|[^'\\])*')|"
        r'(?P<block_comment>/\*.*?\*/)|'
        r'(?P<line_comment>//[^\n]*)|'
        r'(?P<code>[^"\'/]+|/)',
        re.DOTALL
    )

    def replacer(match):
        if match.group('code'):
            code_chunk = match.group('code')
            for pat, repl in COMPILED_TOKENS:
                code_chunk = pat.sub(repl, code_chunk)
            return code_chunk
        return match.group(0)

    return pattern.sub(replacer, content)


def fix_decompiler_artifacts(content):
    """
    Fixes common decompiler artifacts safely.
    """

    # 1. Fix shadowed arrays like: int int[size];
    shadow_pattern = re.compile(
        rf'^([ \t]+)({SHADOW_TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;',
        re.MULTILINE
    )

    for indent, type_name, var_name, size in shadow_pattern.findall(content):
        content = re.sub(
            rf'{indent}{type_name}\s+{var_name}\s*\[',
            f'{indent}{type_name} buffer_{var_name}[',
            content
        )
        content = re.sub(
            rf'\b{var_name}\s*\[(?!\s*\])',
            f'buffer_{var_name}[',
            content
        )

    # 2. Fix invalid array assignments
    assign_pattern = re.compile(
        rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([^;]+)\s*;',
        re.MULTILINE
    )

    def array_to_memcpy(match):
        indent, dtype, name, size, src = match.groups()
        src = src.strip()

        # Keep initializer lists intact
        if src.startswith('{') and src.endswith('}'):
            return f"{indent}{dtype} {name}[{size}] = {src};"

        # Only rewrite if size is numeric
        if not size.isdigit():
            return match.group(0)

        return (
            f"{indent}{dtype} {name}[{size}];\n"
            f"{indent}memcpy({name}, {src}, {size} * sizeof({dtype}));"
        )

    content = assign_pattern.sub(array_to_memcpy, content)

    return content


def fix_linkage_conflicts(content):
    """
    Adds forward declarations for static functions.
    """
    static_func_pattern = re.compile(
        r"^(static\s+[\w\s\*]+?\s+(\w+)\s*\([^)]*\))\s*\{",
        re.MULTILINE
    )

    matches = static_func_pattern.findall(content)
    if not matches:
        return content

    existing_decls = set(re.findall(r"^static\s+.*?;", content, re.MULTILINE))
    new_decls = []

    for full_sig, _ in matches:
        decl = f"{full_sig.strip()};"
        if decl not in existing_decls:
            new_decls.append(decl)

    if new_decls:
        header_block = "\n/* BKA Forward Decls */\n" + "\n".join(new_decls) + "\n"
        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
        pos = includes[-1].end() if includes else 0
        content = content[:pos] + "\n" + header_block + content[pos:]

    return content


def sanitize_codebase(root_path):
    print(f"🧹 Sanitizing: {root_path}")
    patch_count = 0

    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path):
            continue

        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h')):
                    continue

                if filename == "n64_types.h":
                    continue

                filepath = os.path.join(root, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        original = f.read()
                except:
                    continue

                content = safe_token_replacement(original)
                content = fix_decompiler_artifacts(content)

                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)

                if content != original:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Sanitized] {filepath}")

    print(f"✅ Done. {patch_count} files updated.")


if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)