import os
import re
import sys
import traceback

TARGET_DIRS = ["src", "include", "lib", "libultra"]
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
    r'#include\s*[<"]ultratypes\.h[">]',
    r'#include\s*[<"]PR/ultratypes\.h[">]',
]
TYPES_INCLUDE_RE = re.compile('|'.join(TYPES_INCLUDE_PATTERNS))

CORE_TYPE_HEADERS = {"n64_types.h", "ultratypes.h", "ultra64.h", "types.h"}

def is_modern_wrapper(filepath, content):
    if filepath.endswith(('.cpp', '.hpp', '.cc', '.cxx')):
        return True
    path_lower = filepath.replace('\\', '/').lower()
    if "/android/app/" in path_lower or "/jni/" in path_lower or "wrapper" in path_lower:
        return True
    if re.search(r'#include\s*[<"]jni\.h[">]', content) or re.search(r'#include\s*[<"]android/', content):
        return True
    return False

def needs_types_injection(content):
    return not bool(TYPES_INCLUDE_RE.search(content))

def inject_types_include(content, is_c_file=False):
    if is_c_file:
        content = re.sub(r'^[ \t]*#[ \t]*include[ \t]*[<"]n64_types\.h[">][ \t]*\n?', '', content, flags=re.MULTILINE)

    lines = content.split('\n')

    if is_c_file:
        last_include_idx = -1
        for i, line in enumerate(lines):
            s = line.strip()
            if re.match(r'^#[ \t]*include\b', s):
                last_include_idx = i

        if last_include_idx >= 0:
            lines.insert(last_include_idx + 1, '#include <n64_types.h>')
        else:
            lines.insert(0, '#include <n64_types.h>')
        return '\n'.join(lines)

    insert_idx = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith('//') or s.startswith('/*') or s.startswith('*'):
            continue
        if re.match(r'^#[ \t]*pragma[ \t]+once\b', s):
            insert_idx = i + 1
            break
        if re.match(r'^#[ \t]*ifndef\b', s) or re.match(r'^#[ \t]*if[ \t]+!defined\b', s):
            for j in range(i+1, min(i+5, len(lines))):
                if re.match(r'^#[ \t]*define\b', lines[j].strip()):
                    insert_idx = j + 1
                    break
            if insert_idx == 0:
                insert_idx = i + 1
            break
        insert_idx = i
        break

    lines.insert(insert_idx, '#include <n64_types.h>')
    return '\n'.join(lines)

def inject_extern_c(content, filename):
    if not filename.endswith('.h'): return content
    if 'extern "C"' in content or '#ifdef __cplusplus' in content:
        return content

    lines = content.split('\n')
    new_lines = []

    for line in lines:
        match = re.match(r'^[ \t]*#[ \t]*include[ \t]*<([^>]+)>', line)
        if match and '.' not in match.group(1):
            new_lines.append("#ifdef __cplusplus\n}\n#endif")
            new_lines.append(line)
            new_lines.append("#ifdef __cplusplus\nextern \"C\" {\n#endif")
        else:
            new_lines.append(line)

    result = "#ifdef __cplusplus\nextern \"C\" {\n#endif\n\n" + '\n'.join(new_lines) + "\n\n#ifdef __cplusplus\n}\n#endif\n"

    empty_block_pattern = re.compile(r'#ifdef __cplusplus\nextern "C" \{\n#endif\s*#ifdef __cplusplus\n\}\n#endif\s*', re.MULTILINE)
    result = empty_block_pattern.sub('', result)

    merge_pattern = re.compile(r'#ifdef __cplusplus\n\}\n#endif\s*#ifdef __cplusplus\nextern "C" \{\n#endif\s*', re.MULTILINE)
    result = merge_pattern.sub('\n', result)

    return result.strip() + '\n'

def redirect_legacy_includes(content, headers_to_redirect, is_wrapper=False, filename=""):
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
    parts = re.split(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*)', content, flags=re.DOTALL)
    for i in range(0, len(parts), 2):
        if parts[i]:
            code_chunk = parts[i]
            for pat, repl in tokens:
                code_chunk = pat.sub(repl, code_chunk)
            parts[i] = code_chunk
    return "".join(parts)

def apply_android_memory_routing(content, filename):
    """
    Implements Just-In-Time Pointer Translation. 
    """
    if "BKA_TRANSLATE_ADDR" not in content and filename.endswith(('.c', '.h')):
        header = """#include <stdint.h>\n#ifdef __cplusplus\nextern "C" {\n#endif\nextern unsigned int* gN64_Reg_Base;\nextern unsigned int* gN64_PIF_Base;\nextern void InitN64Registers(void);\n#ifdef __cplusplus\n}\n#endif\n#define BKA_GET_REG_BASE() (gN64_Reg_Base ? gN64_Reg_Base : (InitN64Registers(), gN64_Reg_Base))\n#define BKA_GET_PIF_BASE() (gN64_PIF_Base ? gN64_PIF_Base : (InitN64Registers(), gN64_PIF_Base))\n#define BKA_TRANSLATE_ADDR(addr) ( \\\n    (((uintptr_t)(addr) >= 0x04000000) && ((uintptr_t)(addr) < 0x05000000)) ? ((uintptr_t)BKA_GET_REG_BASE() + ((uintptr_t)(addr) - 0x04000000)) : \\\n    (((uintptr_t)(addr) >= 0x1FC00000) && ((uintptr_t)(addr) < 0x1FC01000)) ? ((uintptr_t)BKA_GET_PIF_BASE() + ((uintptr_t)(addr) - 0x1FC00000)) : \\\n    (((uintptr_t)(addr) >= 0xA4000000) && ((uintptr_t)(addr) < 0xA5000000)) ? ((uintptr_t)BKA_GET_REG_BASE() + ((uintptr_t)(addr) - 0xA4000000)) : \\\n    (((uintptr_t)(addr) >= 0xBFC00000) && ((uintptr_t)(addr) < 0xBFC01000)) ? ((uintptr_t)BKA_GET_PIF_BASE() + ((uintptr_t)(addr) - 0xBFC00000)) : \\\n    (uintptr_t)(addr) \\\n)\n\n"""
        content = header + content

    # 1. Match specific literal dereferences: (vu32 *)0xHEX
    content = re.sub(
        r'\(\s*(volatile\s+[us]\d+|v?[us]\d+)\s*\*\s*\)\s*(0x[0-9a-fA-F]+)',
        r'(\1 *)BKA_TRANSLATE_ADDR(\2)',
        content
    )
    
    # 2. Match function-like macros or variables with parentheses: (vu32 *)MACRO(ARGS)
    # This prevents truncating calls like PHYS_TO_K1(0x284)
    content = re.sub(
        r'\(\s*(volatile\s+[us]\d+|v?[us]\d+)\s*\*\s*\)\s*(?!BKA_TRANSLATE_ADDR)([a-zA-Z0-9_]+\s*\((?:[^)(]+|\([^)(]*\))*\))',
        r'(\1 *)BKA_TRANSLATE_ADDR(\2)',
        content
    )
    
    # 3. Match standard variable dereferences: (vu32 *)var 
    # The negative lookahead (?!\s*\() guarantees this regex does not accidentally slice a macro.
    content = re.sub(
        r'\(\s*(volatile\s+[us]\d+|v?[us]\d+)\s*\*\s*\)\s*(?!BKA_TRANSLATE_ADDR)([a-zA-Z0-9_]+)(?!\s*\()',
        r'(\1 *)BKA_TRANSLATE_ADDR(\2)',
        content
    )
    
    # 4. Match explicit offset dereferences: (vu32 *)(var + offset)
    content = re.sub(
        r'\(\s*(volatile\s+[us]\d+|v?[us]\d+)\s*\*\s*\)\s*\(\s*([a-zA-Z0-9_]+)\s*\+\s*(0x[0-9a-fA-F]+|\d+)\s*\)',
        r'(\1 *)BKA_TRANSLATE_ADDR(\2 + \3)',
        content
    )

    # 5. Intercept all global SDK Hardware Access Macros
    content = re.sub(r'#define\s+HW_REG\s*\(\s*reg\s*,\s*type\s*\)\s*\*.*', r'#define HW_REG(reg, type) *(volatile type *)BKA_TRANSLATE_ADDR(reg)', content)
    content = re.sub(r'#define\s+IO_READ\s*\(\s*addr\s*\)\s*\*.*', r'#define IO_READ(addr) (*(vu32 *)BKA_TRANSLATE_ADDR(addr))', content)
    content = re.sub(r'#define\s+IO_WRITE\s*\(\s*addr\s*,\s*data\s*\)\s*\*.*', r'#define IO_WRITE(addr, data) (*(vu32 *)BKA_TRANSLATE_ADDR(addr) = (u32)(data))', content)

    if filename == "os_convert.h":
        content = re.sub(
            r'#define\s+OS_PHYSICAL_TO_K1\s*\(\s*x\s*\).*',
            r'#define OS_PHYSICAL_TO_K1(x) ((void *)BKA_TRANSLATE_ADDR((uintptr_t)(x)|0xA0000000))',
            content
        )
        content = re.sub(
            r'#define\s+OS_PHYSICAL_TO_K0\s*\(\s*x\s*\).*',
            r'#define OS_PHYSICAL_TO_K0(x) ((void *)BKA_TRANSLATE_ADDR((uintptr_t)(x)|0x80000000))',
            content
        )
        content = re.sub(
            r'#define\s+OS_K1_TO_PHYS\s*\(\s*x\s*\).*',
            r'#define OS_K1_TO_PHYS(x) ((uintptr_t)(x) & 0x1FFFFFFF)',
            content
        )
        content = re.sub(
            r'#define\s+OS_K0_TO_PHYS\s*\(\s*x\s*\).*',
            r'#define OS_K0_TO_PHYS(x) ((uintptr_t)(x) & 0x1FFFFFFF)',
            content
        )

    if filename == "R4300.h":
        content = re.sub(
            r'#define\s+PHYS_TO_K1\s*\(\s*x\s*\).*',
            r'#define PHYS_TO_K1(x) ((uintptr_t)BKA_TRANSLATE_ADDR((uintptr_t)(x)|0xA0000000))',
            content
        )
        content = re.sub(
            r'#define\s+PHYS_TO_K0\s*\(\s*x\s*\).*',
            r'#define PHYS_TO_K0(x) ((uintptr_t)BKA_TRANSLATE_ADDR((uintptr_t)(x)|0x80000000))',
            content
        )
        content = re.sub(
            r'#define\s+K1_TO_PHYS\s*\(\s*x\s*\).*',
            r'#define K1_TO_PHYS(x) ((uintptr_t)(x) & 0x1FFFFFFF)',
            content
        )
        content = re.sub(
            r'#define\s+K0_TO_PHYS\s*\(\s*x\s*\).*',
            r'#define K0_TO_PHYS(x) ((uintptr_t)(x) & 0x1FFFFFFF)',
            content
        )

    return content

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

def fix_struct_shadowing(content):
    for shadow_type in ['u8', 's8', 'u16', 's16', 'u32', 's32', 'u64', 's64']:
        pat = re.compile(r'\}\s*' + shadow_type + r'\s*;')
        if pat.search(content):
            content = pat.sub(f'}} {shadow_type}_struct;', content)
            content = content.replace(f".{shadow_type}.", f".{shadow_type}_struct.")
            content = content.replace(f"->{shadow_type}.", f"->{shadow_type}_struct.")
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

        def repl(m): return ' ' * len(m.group(0))
        clean_content = re.sub(r'/\*.*?\*/', repl, content, flags=re.DOTALL)
        clean_content = re.sub(r'//.*', repl, clean_content)
        clean_content = re.sub(r'".*?"', repl, clean_content)
        clean_content = re.sub(r"'.*?'", repl, clean_content)

        func_def_pattern = re.compile(r'^[ \t]*([a-zA-Z_]\w*[ \t\n\*]+)+[a-zA-Z_]\w*[ \t\n]*\([^)]*\)[ \t\n]*\{', re.MULTILINE)

        first_func_match = func_def_pattern.search(clean_content)

        if first_func_match:
            pos = first_func_match.start()
            clean_pre_text = clean_content[:pos]

            last_semi = clean_pre_text.rfind(';')
            last_semi_pos = last_semi + 1 if last_semi != -1 else 0

            last_inc_match = list(re.finditer(r'^[ \t]*#[ \t]*include[^\n]*', clean_pre_text, re.MULTILINE))
            last_inc_pos = last_inc_match[-1].end() if last_inc_match else 0

            last_macro_match = list(re.finditer(r'^[ \t]*#[ \t]*define[^\n]*', clean_pre_text, re.MULTILINE))
            last_macro_pos = last_macro_match[-1].end() if last_macro_match else 0

            insert_idx = max(last_semi_pos, last_inc_pos, last_macro_pos)

            if insert_idx > 0:
                while insert_idx < pos and content[insert_idx] in ' \t\r\n':
                    insert_idx += 1
            else:
                insert_idx = 0

            content = content[:insert_idx] + header_block + content[insert_idx:]
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

                    is_wrapper = is_modern_wrapper(filepath, original_content)
                    content = redirect_legacy_includes(original_content, headers_to_redirect, is_wrapper, filename)

                    if is_wrapper:
                        if content != original_content:
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(content)
                            wrapper_count += 1
                        continue

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
                    content = fix_struct_shadowing(content)
                    content = apply_android_memory_routing(content, filename)

                    if filename.endswith('.c'):
                        content = fix_linkage_conflicts(content)
                        if filename not in CORE_TYPE_HEADERS:
                            content = inject_types_include(content, is_c_file=True)

                    if filename.endswith('.h'):
                        if filename not in CORE_TYPE_HEADERS and needs_types_injection(content):
                            content = inject_types_include(content, is_c_file=False)
                        content = inject_extern_c(content, filename)

                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        patch_count += 1

                except Exception as e:
                    print(f"❌ CRITICAL EXCEPTION in {filepath}:\n{traceback.format_exc()}")
                    continue

    print(f"✅ Sanitization Complete! {patch_count} core files modified. {wrapper_count} wrappers aligned.")

if __name__ == "__main__":
    sanitize_codebase(sys.argv[1] if len(sys.argv) > 1 else ".")
