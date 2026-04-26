import os
import re
import sys

TARGET_DIRS = ["src", "include"]

# Pre-compile the token replacements for performance
# These targets MUST be defined in your n64_types.h
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
COMPILED_TOKENS = [(re.compile(k), v) for k, v in TOKEN_REPLACEMENTS.items()]

SHADOW_TYPES = r'\b(?:u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double)\b'

def safe_token_replacement(content):
    """
    Safely replaces tokens in C/C++ code while ignoring comments and strings.
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

def wrap_shadow_headers(content, filename):
    """Wraps standard headers to prevent namespace collision with N64 symbols."""
    shadow_headers = ['string.h', 'math.h', 'stdlib.h', 'stdio.h', 'stdarg.h', 'stddef.h', 'time.h', 'assert.h', 'stdint.h']
    if filename in shadow_headers:
        if '#include_next' not in content:
            return f"#ifndef BKA_SYS_WRAP_{filename.upper().replace('.','_')}\n#define BKA_SYS_WRAP_{filename.upper().replace('.','_')}\n#ifdef __cplusplus\n#include_next <{filename}>\n#else\n{content}\n#endif\n#endif\n"
    return content

def fix_decompiler_artifacts(content, filename):
    """Fixes common decompiler artifacts like variable shadowing and invalid array assignments."""
    # 1. Fix shadowed variable names
    shadow_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;', re.MULTILINE)
    shadow_matches = shadow_pattern.findall(content)

    for indent, type_name, var_name, size in shadow_matches:
        decl_line = rf'{indent}{type_name}\s+{var_name}\s*\['
        content = re.sub(decl_line, f'{indent}{type_name} buffer_{var_name}[', content)
        content = re.sub(rf'\b{var_name}\s*\[(?!\s*\])', f'buffer_{var_name}[', content)

    # 2. Fix invalid array assignments
    assign_pattern = re.compile(
        rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([^;]+)\s*;',
        re.MULTILINE
    )

    def array_to_memcpy(match):
        indent, dtype, name, size, src = match.groups()
        src = src.strip()
        final_name = f"buffer_{name}" if dtype == name else name

        if src.startswith('{') and src.endswith('}'):
            return f"{indent}{dtype} {final_name}[{size}] = {src};"
        
        # Use n64_memcpy (defined in our cooperative library)
        return f"{indent}{dtype} {final_name}[{size}];\n{indent}n64_memcpy({final_name}, {src}, {size} * sizeof({dtype}));"

    content = assign_pattern.sub(array_to_memcpy, content)

    # 3. Emergency tmp buffer (now using cooperative {0} init)
    if '[tmp]' in content and not re.search(r'\b\w+\s+\**tmp\b\s*(?:\[|;|=)', content):
        tmp_decl = "\n/* BKA Emergency Buffer */\n#ifdef __cplusplus\nstatic thread_local u8 tmp[1024] = {0};\n#else\nstatic _Thread_local u8 tmp[1024] = {0};\n#endif\n"
        content = tmp_decl + content

    return content

def fix_linkage_conflicts(content):
    """Ensures static functions have proper forward declarations to prevent linkage errors."""
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

    if signatures:
        header_block = "\n/* BKA Automated Forward Decls */\n" + "\n".join(signatures) + "\n"
        includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
        pos = includes[-1].end() if includes else 0
        content = content[:pos] + "\n" + header_block + content[pos:]
    return content

def sanitize_codebase(root_path):
    print(f"🧹 Scanning for sanitization: {root_path}")
    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h')): continue
                
                # CRITICAL: Do not sanitize the Master Header itself
                if filename == "n64_types.h": continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        original_content = f.read()
                except: continue

                content = safe_token_replacement(original_content)
                content = fix_decompiler_artifacts(content, filename)
                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)
                content = wrap_shadow_headers(content, filename)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Sanitized] {filepath}")

    print(f"✅ Sanitization Complete! {patch_count} files modified.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
