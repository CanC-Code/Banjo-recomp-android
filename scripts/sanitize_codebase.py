import os
import re
import sys

TARGET_DIRS = ["src", "include"]
CONFLICTING_HEADERS = ["string.h", "time.h", "math.h", "stdlib.h", "stdio.h", "stdarg.h", "stdint.h", "bool.h"]

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
    r"\bvu8\b": "volatile u8",
    r"\bvs8\b": "volatile s8",
    r"\bvu16\b": "volatile u16",
    r"\bvs16\b": "volatile s16",
    r"\bvu32\b": "volatile u32",
    r"\bvs32\b": "volatile s32",
    r"\bvu64\b": "volatile u64",
    r"\bvs64\b": "volatile s64",
    r"\bvf32\b": "volatile f32",
    r"\bvf64\b": "volatile f64",
}
COMPILED_TOKENS = [(re.compile(k), v) for k, v in TOKEN_REPLACEMENTS.items()]

SHADOW_TYPES = r'\b(?:u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double)\b'

TYPES_INCLUDE_PATTERNS = [
    r'#include\s*[<"]n64_types\.h[">]',
    r'#include\s*[<"]ultra64\.h[">]',
    r'#include\s*[<"]PR/ultra64\.h[">]',
    r'#include\s*[<"]2\.0L/ultra64\.h[">]',
    r'#include\s*[<"]core2/core2\.h[">]',
    r'#include\s*[<"]core1/core1\.h[">]',
    r'#include\s*[<"]functions\.h[">]',
    r'#include\s*[<"]structs\.h[">]',
    r'#include\s*[<"]osint\.h[">]',
    r'#include\s*[<"]piint\.h[">]',
    r'#include\s*[<"]PR/os\.h[">]',
    r'#include\s*[<"]n64_bool\.h[">]',
]
TYPES_INCLUDE_RE = re.compile('|'.join(TYPES_INCLUDE_PATTERNS))
N64_TYPES_PREAMBLE = '#include <n64_types.h>\n'

# Define core type headers universally
CORE_TYPE_HEADERS = {"n64_types.h", "ultratypes.h", "ultra64.h", "types.h"}

def is_modern_wrapper(filepath, content):
    """
    Detect if a file is an Android/JNI wrapper or C++ bridging code.
    These files must ONLY have their SDK headers redirected, NO token replacements.
    """
    if filepath.endswith(('.cpp', '.hpp', '.cc', '.cxx')):
        return True
        
    path_lower = filepath.replace('\\', '/').lower()
    
    if "/android/app/" in path_lower or "/jni/" in path_lower or "wrapper" in path_lower:
        return True
    
    if re.search(r'#include\s*[<"]jni\.h[">]', content):
        return True
    if re.search(r'#include\s*[<"]android/', content):
        return True
    return False

def needs_types_injection(content):
    return not bool(TYPES_INCLUDE_RE.search(content))

def inject_types_include(content):
    first_include = re.search(r'^#include', content, re.MULTILINE)
    if first_include:
        pos = first_include.start()
        return content[:pos] + N64_TYPES_PREAMBLE + content[pos:]
    return N64_TYPES_PREAMBLE + content

def inject_extern_c(content, filename):
    """Wrap C headers in extern "C" AFTER the include block to prevent C++ standard library conflicts."""
    if not filename.endswith('.h'): return content
    if 'extern "C"' in content or '#ifdef __cplusplus' in content:
        return content
    
    # Locate the final #include directive in the header
    includes = list(re.finditer(r'^#include.*$', content, re.MULTILINE))
    if includes:
        pos = includes[-1].end()
        # Inject the extern "C" guard safely beneath all system and local includes
        return content[:pos] + "\n\n#ifdef __cplusplus\nextern \"C\" {\n#endif\n" + content[pos:] + "\n\n#ifdef __cplusplus\n}\n#endif\n"
    else:
        # If no includes exist, safe to inject at the very top
        return "#ifdef __cplusplus\nextern \"C\" {\n#endif\n\n" + content + "\n\n#ifdef __cplusplus\n}\n#endif\n"

def redirect_legacy_includes(content, headers_to_redirect, is_wrapper=False, filename=""):
    # Fix: Prevent ALL root type headers from redirecting their own internal ultratypes.h inclusion
    if filename not in CORE_TYPE_HEADERS:
        content = re.sub(r'#include\s*[<"]ultratypes\.h[">]', '/* Redirected */ #include <n64_types.h>', content)
        content = re.sub(r'#include\s*[<"]PR/ultratypes\.h[">]', '/* Redirected */ #include <n64_types.h>', content)

    if not is_wrapper:
        for ch in headers_to_redirect:
            escaped_ch = ch.replace('.', r'\.')
            content = re.sub(rf'#include\s*[<"]{escaped_ch}[">]', f'/* Redirected */ #include <n64_{ch}>', content)

    sdk_headers = [
        'libaudio.h', 'n_libaudio.h', 'os.h', 'rcp.h', 'sptask.h', 'gu.h',
        'mbi.h', 'gbi.h', 'abi.h', 'ultralog.h', 'sp.h', 'region.h', 'sched.h',
        'os_message.h', 'os_libc.h', 'os_thread.h', 'os_si.h', 'os_vi.h',
        'os_pi.h', 'os_ai.h', 'os_pfs.h', 'os_motor.h', 'os_time.h', 'os_flash.h',
        'os_internal.h', 'os_cont.h', 'os_cache.h', 'os_debug.h', 'os_eeprom.h',
        'os_error.h', 'os_exception.h', 'os_gbpak.h', 'os_gio.h', 'os_host.h',
        'os_rdp.h', 'os_reg.h', 'os_rsp.h', 'os_system.h', 'os_tlb.h', 'os_version.h',
        'os_voice.h', 'PRimage.h', 'R4300.h', 'gs2dex.h', 'gt.h', 'leo.h',
        'leoappli.h', 'ramrom.h', 'rdb.h', 'rmon.h', 'ucode.h', 'ucode_debug.h',
        'ultraerror.h', 'uportals.h', 'n_abi.h', 'n_libaudio_s_to_n.h',
        'os_internal_debug.h', 'os_internal_error.h', 'os_internal_exception.h',
        'os_internal_gio.h', 'os_internal_host.h', 'os_internal_reg.h',
        'os_internal_rsp.h', 'os_internal_si.h', 'os_internal_thread.h',
        'os_internal_tlb.h'
    ]

    for header in sdk_headers:
        content = re.sub(rf'#include\s*<(?![pP][rR]/){header}>', f'#include <PR/{header}>', content)
        content = re.sub(rf'#include\s*"(?![pP][rR]/){header}"', f'#include "PR/{header}"', content)

    content = re.sub(r'#include\s*[<"]PR/n_synth\.h[">]', '#include "n_synth.h"', content)
    content = re.sub(r'#include\s*[<"]PR/n_synthInternals\.h[">]', '#include "n_synthInternals.h"', content)
    content = re.sub(r'#include\s*[<"]PR/synthInternals\.h[">]', '#include "synthInternals.h"', content)
    content = re.sub(r'#include\s*[<"]PR/n_libaudio_sn\.h[">]', '#include "n_libaudio_sn.h"', content)

    return content

def safe_token_replacement(content, tokens=COMPILED_TOKENS):
    pattern = re.compile(
        r'(?P<string>"(?:\\.|[^"\\])*")|(?P<char>\'(?:\\.|[^\'\\])*\')|'
        r'(?P<block_comment>/\*.*?\*/)|(?P<line_comment>//[^\n]*)|'
        r'(?P<code>[^"\'/]+|/)', re.DOTALL
    )

    def replacer(match):
        if match.group('code'):
            code_chunk = match.group('code')
            for pat, repl in tokens:
                code_chunk = pat.sub(repl, code_chunk)
            return code_chunk
        return match.group(0)

    return pattern.sub(replacer, content)

def fix_decompiler_artifacts(content, filename):
    shadow_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;', re.MULTILINE)
    shadow_matches = shadow_pattern.findall(content)

    for indent, type_name, var_name, size in shadow_matches:
        decl_line = rf'{indent}{type_name}\s+{var_name}\s*\['
        content = re.sub(decl_line, f'{indent}{type_name} buffer_{var_name}[', content)
        content = re.sub(rf'\b{var_name}\s*\[(?!\s*\])', f'buffer_{var_name}[', content)

    assign_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([^;]+)\s*;', re.MULTILINE)

    def array_to_memcpy(match):
        indent, dtype, name, size, src = match.groups()
        src = src.strip()
        if src.startswith('{') or src.startswith('"') or src.startswith("'"): 
            return match.group(0)
        return f"{indent}{dtype} {name}[{size}];\n{indent}n64_memcpy({name}, {src}, {size} * sizeof({dtype}));"

    content = assign_pattern.sub(array_to_memcpy, content)
    return content

def fix_linkage_conflicts(content):
    static_def_pattern = re.compile(r"^static\s+([\w\s\*]+\b(\w+)\s*\([^)]*\)\s*\{)", re.MULTILINE)
    for match in static_def_pattern.finditer(content):
        full_sig = match.group(1)
        func_name = match.group(2)

        proto_pattern = re.compile(r"^[ \t]*([\w\s\*]*\b" + re.escape(func_name) + r"\s*\([^)]*\)\s*;)", re.MULTILINE)
        has_non_static_proto = False
        for p_match in proto_pattern.finditer(content):
            proto_line = p_match.group(0)
            if "static" not in proto_line and "typedef" not in proto_line:
                has_non_static_proto = True
                break

        if has_non_static_proto:
            content = content.replace("static " + full_sig, full_sig)

    static_func_pattern = re.compile(r"^(static\s+[\w\s\*]+?(\w+)\s*\([^)]*\)\s*)\{", re.MULTILINE)
    matches = static_func_pattern.findall(content)
    if not matches: return content

    signatures = []
    added_funcs = set()

    for full_sig, func_name in matches:
        has_prototype = bool(re.search(rf"\b{re.escape(func_name)}\s*\([^)]*\)\s*;", content))

        if not has_prototype and func_name not in added_funcs:
            decl = f"{full_sig.strip()};"
            signatures.append(decl)
            added_funcs.add(func_name)

    if signatures:
        header_block = "\n/* Automated Forward Decls */\n" + "\n".join(signatures) + "\n\n"
        any_func_pattern = re.compile(r"^([a-zA-Z_][\w\s\*]*\s+[a-zA-Z_]\w*\s*\([^)]*\)\s*)\{", re.MULTILINE)
        first_func_match = any_func_pattern.search(content)

        if first_func_match:
            pos = first_func_match.start()
            content = content[:pos] + header_block + content[pos:]
        else:
            content = content + "\n" + header_block

    return content

def sanitize_codebase(root_path):
    print(f"🧹 Scanning for sanitization: {root_path}")

    include_search_dirs = [
        "include",
        os.path.join("include", "2.0L"),
        os.path.join("include", "2.0L", "PR"),
    ]
    
    headers_to_redirect = set()
    
    for ch in CONFLICTING_HEADERS:
        for sub_dir in include_search_dirs:
            old_path = os.path.join(root_path, sub_dir, ch)
            new_path = os.path.join(root_path, sub_dir, f"n64_{ch}")
            
            if os.path.exists(old_path) or os.path.exists(new_path):
                headers_to_redirect.add(ch)
                
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    print(f"  [Renamed] {sub_dir}/{ch} -> {sub_dir}/n64_{ch} to resolve shadowing")

    patch_count = 0
    wrapper_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')): continue

                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        original_content = f.read()
                except Exception: continue

                is_wrapper = is_modern_wrapper(filepath, original_content)

                # EVERY file (including wrappers and SDK) gets its legacy headers safely mapped
                content = redirect_legacy_includes(original_content, headers_to_redirect, is_wrapper, filename)

                if is_wrapper:
                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        wrapper_count += 1
                        print(f"  [Wrapper Aligned] {filepath} (Redirected SDK headers only)")
                    continue
                    
                # --- Core Game Code Only ---
                
                if filename in CORE_TYPE_HEADERS:
                    bool_tokens = [
                        (re.compile(r"\bbool\b"), "n64_bool"),
                        (re.compile(r"\btrue\b"), "TRUE"),
                        (re.compile(r"\bfalse\b"), "FALSE")
                    ]
                    content = safe_token_replacement(content, bool_tokens)
                else:
                    content = safe_token_replacement(content, COMPILED_TOKENS)
                
                content = fix_decompiler_artifacts(content, filename)

                if filename.endswith('.c'):
                    content = fix_linkage_conflicts(content)
                
                # IMPORTANT: Inject Types Header BEFORE parsing includes for extern "C"
                if filename.endswith(('.c', '.h')):
                    if filename not in CORE_TYPE_HEADERS and needs_types_injection(content):
                        content = inject_types_include(content)

                # IMPORTANT: Inject extern "C" AFTER the types header has settled
                if filename.endswith('.h'):
                    content = inject_extern_c(content, filename)

                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Sanitized] {filepath}")

    print(f"✅ Sanitization Complete! {patch_count} core files modified. {wrapper_count} wrappers aligned.")

if __name__ == "__main__":
    sanitize_codebase(sys.argv[1] if len(sys.argv) > 1 else ".")
