#!/usr/bin/env python3
import os
import re
import traceback

# === CONFIGURATION ===
# Replaced tokens for standardization
TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "TRUE",
    r"\bfalse\b": "FALSE"
}

CORE_TYPE_HEADERS = [
    'n64_types.h', 'ultra64.h', 'ultratypes.h',
    'types.h', 'n64_types_compat.h'
]

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

# === HELPER FUNCTIONS ===

def is_modern_wrapper(filepath, content):
    path_lower = filepath.lower()
    if filepath.endswith(('.cpp', '.hpp', '.cc', '.cxx')):
        return True
    if "/android/app/" in path_lower or "/jni/" in path_lower or "wrapper" in path_lower:
        return True
    if re.search(r'#include\s*[<"]jni\.h[">]', content) or re.search(r'#include\s*[<"]android/', content):
        return True
    return False

def needs_types_injection(content):
    return not bool(TYPES_INCLUDE_RE.search(content))

def inject_types_include(content, is_c_file=False):
    if not needs_types_injection(content):
        return content

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
        if not s or s.startswith('//') or s.startswith('/*'):
            continue
        if re.match(r'^#[ \t]*pragma[ \t]+once\b', s):
            insert_idx = i + 1
            break
        if re.match(r'^#[ \t]*ifndef\b', s) or re.match(r'^#[ \t]*define\b', s):
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

    result = "#ifdef __cplusplus\nextern \"C\" {\n#endif\n\n" + '\n'.join(new_lines) + "\n#ifdef __cplusplus\n}\n#endif"
    
    empty_block_pattern = re.compile(r'#ifdef __cplusplus\nextern "C" \{\n#endif\n#ifdef __cplusplus\n\}\n#endif\n', re.MULTILINE)
    result = empty_block_pattern.sub('', result)
    
    merge_pattern = re.compile(r'#ifdef __cplusplus\n\}\n#endif\n#ifdef __cplusplus\nextern "C" \{\n#endif\n', re.MULTILINE)
    result = merge_pattern.sub('\n', result)
    
    return result.strip() + '\n'

def redirect_legacy_includes(content, headers_to_redirect, is_wrapper, filename):
    if filename not in CORE_TYPE_HEADERS:
        content = re.sub(r'#include\s*[<"]ultratypes\.h[">]', '#include <n64_types.h>', content)
        content = re.sub(r'#include\s*[<"]PR/ultratypes\.h[">]', '#include <n64_types.h>', content)

    if not is_wrapper:
        for ch in headers_to_redirect:
            escaped_ch = ch.replace('.', r'\.')
            content = re.sub(rf'#include\s*[<"]{escaped_ch}[">]', f'#include <n64_{ch}>', content)

    sdk_headers = [
        'libaudio.h', 'n_libaudio.h', 'os.h', 'rcp.h', 'sptask.h', 'gu.h',
        'mbi.h', 'gbi.h', 'abi.h', 'ultralog.h', 'sp.h', 'region.h',
        'os_message.h', 'os_libc.h', 'os_thread.h', 'os_si.h', 'os_pi.h',
        'os_ai.h', 'os_pfs.h', 'os_motor.h', 'os_time.h', 'os_vi.h',
        'os_internal.h', 'os_cont.h', 'os_cache.h', 'os_debug.h',
        'os_error.h', 'os_exception.h', 'os_gbpak.h', 'os_gio.h',
        'os_rdp.h', 'os_reg.h', 'os_rsp.h', 'os_system.h', 'os_tlb.h',
        'os_voice.h', 'PRimage.h', 'R4300.h', 'gs2dex.h', 'gu_hal.h',
        'leoappli.h', 'ramrom.h', 'rdb.h', 'rmon.h', 'ucode.h', 'ultrahost.h',
        'ultraerror.h', 'uportals.h', 'n_abi.h', 'n_libaudio_s_sn.h',
        'os_internal_debug.h', 'os_internal_error.h', 'os_internal_exception.h',
        'os_internal_gio.h', 'os_internal_host.h', 'os_internal_reg.h',
        'os_internal_rsp.h', 'os_internal_si.h', 'os_internal_thread.h',
        'os_internal_tlb.h'
    ]

    for header in sdk_headers:
        content = re.sub(rf'#include\s*<(?![pP][rR]/){header}>', f'#include <PR/{header}>', content)
        content = re.sub(rf'#include\s*"(?![pP][rR]/){header}"', f'#include "PR/{header}"', content)

    content = re.sub(r'#include\s*[<"]PR/n_synth\.h[">]', '#include <n64_n_synth.h>', content)
    content = re.sub(r'#include\s*[<"]PR/n_synthInternals\.h[">]', '#include <n64_n_synthInternals.h>', content)
    content = re.sub(r'#include\s*[<"]PR/synthInternals\.h[">]', '#include <n64_synthInternals.h>', content)
    content = re.sub(r'#include\s*[<"]PR/n_libaudio_sn\.h[">]', '#include <n64_n_libaudio_sn.h>', content)

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
    if "BKA_TRANSLATE_ADDR" in content or not filename.endswith(('.c', '.cpp', '.h', '.hpp')):
        return content

    header = """#ifndef BKA_SAFE_BASE_INCLUDED
#define BKA_SAFE_BASE_INCLUDED
#ifdef __cplusplus
extern "C" {
#endif
extern void* calloc(unsigned long, unsigned long);
extern unsigned int* gN64_Reg_Base;
extern unsigned int* gN64_PIF_Base;
extern void InitN64Registers(void);
#ifdef __cplusplus
}
#endif
static inline unsigned int* BKA_GetSafeRegBase(void) {
    if (gN64_Reg_Base) return gN64_Reg_Base;
    InitN64Registers();
    return gN64_Reg_Base ? gN64_Reg_Base : (unsigned int*)0;
}
static inline unsigned int* BKA_GetSafePifBase(void) {
    if (gN64_PIF_Base) return gN64_PIF_Base;
    InitN64Registers();
    return gN64_PIF_Base ? gN64_PIF_Base : (unsigned int*)0;
}
#endif
#define BKA_GET_REG_BASE() BKA_GetSafeRegBase()
#define BKA_GET_PIF_BASE() BKA_GetSafePifBase()
#define BKA_MASK32(a) ((unsigned long)(a) & 0xFFFFFFFF)
#define BKA_TRANSLATE_ADDR(addr) ( \\
    (BKA_MASK32(addr) >= 0x04000000 && BKA_MASK32(addr) < 0x05000000) ? ((unsigned int)((unsigned char*)BKA_GET_REG_BASE() + (BKA_MASK32(addr) - 0x04000000))) : \\
    (BKA_MASK32(addr) >= 0x1FC00000 && BKA_MASK32(addr) < 0x1FC01000) ? ((unsigned int)((unsigned char*)BKA_GET_PIF_BASE() + (BKA_MASK32(addr) - 0x1FC00000))) : \\
    (BKA_MASK32(addr) >= 0xA4000000 && BKA_MASK32(addr) < 0xA5000000) ? ((unsigned int)((unsigned char*)BKA_GET_REG_BASE() + (BKA_MASK32(addr) - 0xA4000000))) : \\
    (BKA_MASK32(addr) >= 0xBFC00000 && BKA_MASK32(addr) < 0xBFC01000) ? ((unsigned int)((unsigned char*)BKA_GET_PIF_BASE() + (BKA_MASK32(addr) - 0xBFC00000))) : \\
    (unsigned long)(addr) \\
)\n\n"""
    content = header + content
    ptr_pat = r'^([ \t]+)\(\s*(volatile\s+[us]\d+|v?[us]\d+)\s*\*\s*\)\s*'
    content = re.sub(ptr_pat + r'(0x[0-9a-fA-F]+)', r'\1(\2 *)BKA_TRANSLATE_ADDR(\3)', content, flags=re.MULTILINE)
    content = re.sub(ptr_pat + r'(?!BKA_TRANSLATE_ADDR)([a-zA-Z_]\w*)', r'\1(\2 *)BKA_TRANSLATE_ADDR(\3)', content, flags=re.MULTILINE)
    content = re.sub(r'#define\s+HW_REG\s*\(\s*reg\s*,\s*type\s*\)\s*\(.*?\)', r'#define HW_REG(reg, type) (*((volatile type *)BKA_TRANSLATE_ADDR(reg)))', content)
    content = re.sub(r'#define\s+IO_READ\s*\(\s*addr\s*\)\s*\(.*?\)', r'#define IO_READ(addr) (*((volatile u32 *)BKA_TRANSLATE_ADDR(addr)))', content)
    content = re.sub(r'#define\s+IO_WRITE\s*\(\s*addr\s*,\s*data\s*\)\s*\(.*?\)', r'#define IO_WRITE(addr, data) (*((volatile u32 *)BKA_TRANSLATE_ADDR(addr)) = (u32)(data))', content)

    if filename == "os_convert.h":
        content = re.sub(r'#define\s+OS_PHYSICAL_TO_K1\s*\(\s*x\s*\).*', r'#define OS_PHYSICAL_TO_K1(x) ((void *)(((unsigned int)(x) >= 0x04000000 && (unsigned int)(x) < 0x05000000) ? ((unsigned char*)BKA_GET_REG_BASE() + ((unsigned int)(x) - 0x04000000)) : ((unsigned int)(x) | 0xA0000000)))', content)
        content = re.sub(r'#define\s+OS_PHYSICAL_TO_K0\s*\(\s*x\s*\).*', r'#define OS_PHYSICAL_TO_K0(x) ((void *)(((unsigned int)(x) >= 0x04000000 && (unsigned int)(x) < 0x05000000) ? ((unsigned char*)BKA_GET_REG_BASE() + ((unsigned int)(x) - 0x04000000)) : ((unsigned int)(x) | 0x80000000)))', content)
        content = re.sub(r'#define\s+OS_K1_TO_PHYS\s*\(\s*x\s*\).*', r'#define OS_K1_TO_PHYS(x) (BKA_GET_REG_BASE() && ((unsigned int)(x) >= (unsigned int)BKA_GET_REG_BASE() && (unsigned int)(x) < (unsigned int)BKA_GET_REG_BASE() + 0x1000000) ? ((unsigned int)(x) - (unsigned int)BKA_GET_REG_BASE() + 0x04000000) : ((unsigned int)(x) & 0x1FFFFFFF))', content)
        content = re.sub(r'#define\s+OS_K0_TO_PHYS\s*\(\s*x\s*\).*', r'#define OS_K0_TO_PHYS(x) (BKA_GET_REG_BASE() && ((unsigned int)(x) >= (unsigned int)BKA_GET_REG_BASE() && (unsigned int)(x) < (unsigned int)BKA_GET_REG_BASE() + 0x1000000) ? ((unsigned int)(x) - (unsigned int)BKA_GET_REG_BASE() + 0x04000000) : ((unsigned int)(x) & 0x1FFFFFFF))', content)

    if filename == "R4300.h":
        content = re.sub(r'#define\s+PHYS_TO_K1\s*\(\s*x\s*\).*', r'#define PHYS_TO_K1(x) (((unsigned int)(x) >= 0x04000000 && (unsigned int)(x) < 0x05000000) ? ((unsigned int)BKA_GET_REG_BASE() + ((unsigned int)(x) - 0x04000000)) : ((unsigned int)(x) | 0xA0000000))', content)
        content = re.sub(r'#define\s+PHYS_TO_K0\s*\(\s*x\s*\).*', r'#define PHYS_TO_K0(x) (((unsigned int)(x) >= 0x04000000 && (unsigned int)(x) < 0x05000000) ? ((unsigned int)BKA_GET_REG_BASE() + ((unsigned int)(x) - 0x04000000)) : ((unsigned int)(x) | 0x80000000))', content)
        content = re.sub(r'#define\s+K1_TO_PHYS\s*\(\s*x\s*\).*', r'#define K1_TO_PHYS(x) (BKA_GET_REG_BASE() && ((unsigned int)(x) >= (unsigned int)BKA_GET_REG_BASE() && (unsigned int)(x) < (unsigned int)BKA_GET_REG_BASE() + 0x1000000) ? ((unsigned int)(x) - (unsigned int)BKA_GET_REG_BASE() + 0x04000000) : ((unsigned int)(x) & 0x1FFFFFFF))', content)
        content = re.sub(r'#define\s+K0_TO_PHYS\s*\(\s*x\s*\).*', r'#define K0_TO_PHYS(x) (BKA_GET_REG_BASE() && ((unsigned int)(x) >= (unsigned int)BKA_GET_REG_BASE() && (unsigned int)(x) < (unsigned int)BKA_GET_REG_BASE() + 0x1000000) ? ((unsigned int)(x) - (unsigned int)BKA_GET_REG_BASE() + 0x04000000) : ((unsigned int)(x) & 0x1FFFFFFF))', content)

    return content

def fix_decompiler_artifacts(content, filename):
    shadow_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z_]\w*)\s*\[\s*([^\]]+)\s*\]\s*;\s*', re.MULTILINE)
    shadow_matches = shadow_pattern.findall(content)

    for indent, type_name, var_name, size in shadow_matches:
        decl_line = rf'{indent}{type_name}\s+{var_name}\s*\[\s*{re.escape(size)}\s*\]\s*;'
        content = re.sub(decl_line, f'{indent}{type_name} buf_{var_name}[{size}];\n{indent}{type_name}* {var_name} = buf_{var_name};', content)
        content = re.sub(rf'\b{var_name}\s*\[(?!\s*\])', f'buf_{var_name}[', content)

    # Re-integrated memcpy generation for array assignments
    assign_pattern = re.compile(rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z_]\w*)\s*\[\s*([^\]]+)\s*\]\s*=\s*([^;]+)\s*;', re.MULTILINE)
    
    def array_to_memcpy(match):
        indent, dtype, name, size, src = match.groups()
        src = src.strip()
        if src.startswith('{') or src.startswith('"') or src.startswith('\''):
            return match.group(0)
        return f"{indent}{dtype} {name}[{size}];\n{indent}n64_memcpy({name}, {src}, {size} * sizeof({dtype}));"

    content = assign_pattern.sub(array_to_memcpy, content)
    return content

def fix_struct_shadowing(content):
    for shadow_type in ['u8', 's8', 'u16', 's16', 'u32', 's32', 'f32']:
        pat = re.compile(r'\}\s*' + shadow_type + r'\s*;')
        if pat.search(content):
            content = pat.sub(f'}} {shadow_type}_struct;', content)
            content = content.replace(f".{shadow_type}.", f".{shadow_type}_struct.")
            content = content.replace(f"->{shadow_type}.", f"->{shadow_type}_struct.")
    return content

def fix_linkage_conflicts(content):
    # 1. Extern vs Static conflict resolution
    extern_pattern = re.compile(r"^[ \t]*extern\s+((?:[\w\s\*]+?)\s+([a-zA-Z_]\w*)\s*\([^;]*\));", re.MULTILINE)
    for match in extern_pattern.finditer(content):
        full_sig, func_name = match.group(1), match.group(2)
        if re.search(r"^[ \t]*(?!static\b|typedef\b)[\w\s\*]*\b" + re.escape(func_name) + r"\b\s*\(", content, re.MULTILINE):
            continue
            
        static_func_pattern = re.compile(r"^(static\s+[\w\s\*]+?\b" + re.escape(func_name) + r"\b\s*\([^;]+?\))\s*\{", re.MULTILINE)
        if static_func_pattern.search(content):
             content = content.replace(match.group(0), f"/* Removed conflicting extern: {match.group(0)} */")

    # 2. Automated Forward Declarations for Static Functions
    sigs, added = [], set()
    custom_types = set()
    KNOWN_GLOBALS = {
        'Actor', 'ActorMarker', 'Marker', 'Gfx', 'Vtx', 'Mtx', 'OSMesg',
        'u8', 's8', 'u16', 's16', 'u32', 's32', 'u64', 's64', 'f32', 'f64'
    }

    clean = re.sub(r'("(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*)', '', content, flags=re.DOTALL)
    existing_protos = set(re.findall(r'\b(\w+)\s*\([^;{]*\)\s*;', clean))

    for match in re.finditer(r"^[ \t]*static\s+([^{;]+)\s*\{", content, re.MULTILINE):
        full_def_sig = match.group(1).strip()
        name_match = re.search(r'(\w+)\s*\(', full_def_sig)
        if name_match:
            name = name_match.group(1)
            if name not in existing_protos and name not in added:
                sigs.append(f"static {full_def_sig};")
                added.add(name)
                found_ptr_types = re.findall(r'\b([a-zA-Z_]\w*)\s*\*', full_def_sig)
                for t in found_ptr_types:
                    if t in KNOWN_GLOBALS: continue
                    if t[0].isupper() and not (len(t) > 1 and t[1].isupper()):
                        continue
                    if re.search(rf'\btypedef\s+[^;]+\b{t}\s*;', content): continue
                    custom_types.add(t)

    if sigs:
        type_decls = [f"typedef struct {t} {t};" for t in sorted(custom_types)]
        block = "\n/* Automated Forward Decls for Linkage Fix */\n"
        if type_decls: block += "\n".join(type_decls) + "\n"
        block += "\n".join(sigs) + "\n\n"

        lines = content.split('\n')
        last_include_idx = -1
        for i, line in enumerate(lines):
            if re.match(r'^#[ \t]*include\b', line.strip()):
                last_include_idx = i
        if last_include_idx != -1: lines.insert(last_include_idx + 1, block)
        else: lines.insert(0, block)
        content = '\n'.join(lines)
        
    return content

# === MAIN LOGIC ===

def sanitize_codebase(root_path):
    print("Starting Deep Codebase Sanitization for Android Recompilation...")
    
    headers_to_redirect = [
        'types.h', 'math.h', 'memory.h', 'string.h',
        'stdarg.h', 'stddef.h', 'stdlib.h', 'assert.h'
    ]
    
    include_search_dirs = [
        "include",
        os.path.join("include", "2.0L"),
        os.path.join("include", "2.0L", "PR"),
        os.path.join("include", "core2"),
    ]

    for ch in headers_to_redirect:
        for sub_dir in include_search_dirs:
            old_path = os.path.join(root_path, sub_dir, ch)
            new_path = os.path.join(root_path, sub_dir, f"n64_{ch}")
            if os.path.exists(old_path) or os.path.exists(new_path):
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    print(f"  [Renamed] {sub_dir}/{ch} -> {sub_dir}/n64_{ch}")

    patch_count = 0
    wrapper_count = 0

    for subdir, _, files in os.walk(root_path):
        if '/build/' in subdir.replace('\\', '/') or '/.git/' in subdir.replace('\\', '/'):
            continue

        for filename in files:
            if filename.endswith(('.h', '.c', '.cpp', '.hpp')):
                filepath = os.path.join(subdir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        original_content = f.read()

                    is_wrapper = is_modern_wrapper(filepath, original_content)
                    content = redirect_legacy_includes(original_content, headers_to_redirect, is_wrapper, filename)

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
                            content = inject_types_include(content, True)

                    if filename.endswith('.h'):
                        if filename not in CORE_TYPE_HEADERS and not is_wrapper:
                            content = inject_types_include(content, False)
                        content = inject_extern_c(content, filename)

                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(content)
                        if is_wrapper:
                            wrapper_count += 1
                        else:
                            patch_count += 1

                except Exception as e:
                    print(f"❌ CRITICAL EXCEPTION in {filepath}:\n{traceback.format_exc()}")
                    continue

    print(f"\nSanitization Complete: {patch_count} native files, {wrapper_count} wrappers patched.")

if __name__ == "__main__":
    # Get the root of the Banjo-recomp-android repository
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Define all directories that need sanitization
    target_dirs = [
        os.path.join(repo_root, "src"),
        os.path.join(repo_root, "include"),
        os.path.join(repo_root, "Android", "app", "src", "main", "cpp")
    ]
    
    for t_dir in target_dirs:
        if os.path.exists(t_dir):
            print(f"--- Processing directory: {t_dir} ---")
            sanitize_codebase(t_dir)
        else:
            print(f"Warning: Target directory not found: {t_dir}")
