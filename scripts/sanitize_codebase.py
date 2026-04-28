import os
import re
import sys

TARGET_DIRS = ["src", "include"]
CONFLICTING_HEADERS = ["string.h", "time.h", "math.h", "stdlib.h", "stdio.h", "stdarg.h", "stdint.h"]

# Pre-compile the token replacements for performance
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

def redirect_legacy_includes(content):
    """Fixes missing PR/ prefixes and redirects ultratypes."""
    content = re.sub(r'#include\s*[<"]ultratypes\.h[">]', '/* Redirected */ #include <n64_types.h>', content)
    content = re.sub(r'#include\s*[<"]PR/ultratypes\.h[">]', '/* Redirected */ #include <n64_types.h>', content)

    # Redirect shadowed standard headers
    for ch in CONFLICTING_HEADERS:
        escaped_ch = ch.replace('.', r'\.')
        content = re.sub(rf'#include\s*[<"]{escaped_ch}[">]', f'/* Redirected */ #include <n64_{ch}>', content)

    # Expanded SDK headers that MUST have PR/ prefix
    sdk_headers = [
        'libaudio.h', 'n_libaudio.h', 'os.h', 'rcp.h', 'sptask.h', 'gu.h', 
        'mbi.h', 'gbi.h', 'abi.h', 'ultralog.h', 'sp.h', 'region.h', 'sched.h',
        'os_message.h', 'os_libc.h', 'os_thread.h', 'os_si.h', 'os_vi.h',
        'os_pi.h', 'os_ai.h', 'os_pfs.h', 'os_motor.h', 'os_time.h', 'os_flash.h',
        'n_synth.h', 'n_synthInternals.h', 'n_libaudio_sn.h'
    ]
    
    for header in sdk_headers:
        content = re.sub(rf'#include\s*<(?![pP][rR]/){header}>', f'#include <PR/{header}>', content)
        content = re.sub(rf'#include\s*"(?![pP][rR]/){header}"', f'#include "PR/{header}"', content)

    return content

def safe_token_replacement(content):
    """Replaces tokens while avoiding strings and comments."""
    pattern = re.compile(
        r'(?P<string>"(?:\\.|[^"\\])*")|(?P<char>\'(?:\\.|[^\'\\])*\')|'
        r'(?P<block_comment>/\*.*?\*/)|(?P<line_comment>//[^\n]*)|'
        r'(?P<code>[^"\'/]+|/)', re.DOTALL
    )

    def replacer(match):
        if match.group('code'):
            code_chunk = match.group('code')
            for pat, repl in COMPILED_TOKENS:
                code_chunk = pat.sub(repl, code_chunk)
            return code_chunk
        return match.group(0)

    return pattern.sub(replacer, content)

def fix_decompiler_artifacts(content, filename):
    # Fix shadowed variable names (u8 u8[10] -> u8 buffer_u8[10])
    shadow_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;', re.MULTILINE)
    shadow_matches = shadow_pattern.findall(content)

    for indent, type_name, var_name, size in shadow_matches:
        decl_line = rf'{indent}{type_name}\s+{var_name}\s*\['
        content = re.sub(decl_line, f'{indent}{type_name} buffer_{var_name}[', content)
        content = re.sub(rf'\b{var_name}\s*\[(?!\s*\])', f'buffer_{var_name}[', content)

    # Convert illegal array assignments to memcpy
    assign_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([^;]+)\s*;', re.MULTILINE)
    def array_to_memcpy(match):
        indent, dtype, name, size, src = match.groups()
        src = src.strip()
        if src.startswith('{'): return match.group(0)
        return f"{indent}{dtype} {name}[{size}];\n{indent}n64_memcpy({name}, {src}, {size} * sizeof({dtype}));"
    
    content = assign_pattern.sub(array_to_memcpy, content)
    return content

def fix_linkage_conflicts(content):
    """Identifies missing forward declarations and inserts them safely below typedefs."""
    static_func_pattern = re.compile(r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\)\s*)\{", re.MULTILINE)
    matches = static_func_pattern.findall(content)
    if not matches: return content

    signatures = []
    added_funcs = set()
    
    for full_sig, func_name in matches:
        # Search the entire file for an existing prototype of this function (static or non-static)
        # Looks for instances of: func_name( ... );
        has_prototype = bool(re.search(rf"\b{re.escape(func_name)}\s*\([^)]*\)\s*;", content))
        
        if not has_prototype and func_name not in added_funcs:
            decl = f"{full_sig.strip()};"
            signatures.append(decl)
            added_funcs.add(func_name)

    if signatures:
        header_block = "\n/* Automated Forward Decls */\n" + "\n".join(signatures) + "\n\n"
        
        # Locate the first actual function definition to safely insert declarations AFTER all structs/typedefs
        any_func_pattern = re.compile(r"^([a-zA-Z_][\w\s\*]*\s+[a-zA-Z_]\w*\s*\([^)]*\)\s*)\{", re.MULTILINE)
        first_func_match = any_func_pattern.search(content)
        
        if first_func_match:
            pos = first_func_match.start()
            content = content[:pos] + header_block + content[pos:]
        else:
            # Fallback if no clean match is found
            content = content + "\n" + header_block
            
    return content

def sanitize_codebase(root_path):
    print(f"🧹 Scanning for sanitization: {root_path}")
    
    # Proactively rename all potentially conflicting standard headers
    for ch in CONFLICTING_HEADERS:
        for sub_dir in ["include", os.path.join("include", "2.0L")]:
            old_path = os.path.join(root_path, sub_dir, ch)
            new_path = os.path.join(root_path, sub_dir, f"n64_{ch}")
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                print(f"  [Renamed] {sub_dir}/{ch} -> {sub_dir}/n64_{ch} to resolve shadowing")

    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h')): continue
                if filename == "n64_types.h": continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        original_content = f.read()
                except Exception: continue

                content = redirect_legacy_includes(original_content)
                content = safe_token_replacement(content)
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
    sanitize_codebase(sys.argv[1] if len(sys.argv) > 1 else ".")
