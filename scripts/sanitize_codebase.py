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
CORE_TYPE_HEADERS = {"n64_types.h", "ultratypes.h", "ultra64.h", "types.h"}

def is_modern_wrapper(filepath, content):
    if filepath.endswith(('.cpp', '.hpp', '.cc', '.cxx')): return True
    path_lower = filepath.replace('\\', '/').lower()
    if any(x in path_lower for x in ["/android/app/", "/jni/", "wrapper"]): return True
    return bool(re.search(r'#include\s*[<"]jni\.h[">]', content))

def inject_types_include(content, is_c_file=False):
    if is_c_file:
        content = re.sub(r'^[ \t]*#[ \t]*include[ \t]*[<"]n64_types\.h[">][ \t]*\n?', '', content, flags=re.MULTILINE)
    lines = content.split('\n')
    if is_c_file:
        last_idx = -1
        for i, line in enumerate(lines):
            if re.match(r'^#[ \t]*include\b', line.strip()): last_idx = i
        lines.insert(last_idx + 1, '#include <n64_types.h>') if last_idx >= 0 else lines.insert(0, '#include <n64_types.h>')
        return '\n'.join(lines)
    
    insert_idx = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or any(s.startswith(x) for x in ['//', '/*', '*']): continue
        if re.match(r'^#[ \t]*pragma[ \t]+once\b', s):
            insert_idx = i + 1; break
        if re.match(r'^#[ \t]*if(?:ndef\b| !defined\b)', s):
            for j in range(i+1, min(i+5, len(lines))):
                if re.match(r'^#[ \t]*define\b', lines[j].strip()):
                    insert_idx = j + 1; break
            if insert_idx == 0: insert_idx = i + 1
            break
        insert_idx = i; break
    lines.insert(insert_idx, '#include <n64_types.h>')
    return '\n'.join(lines)

def apply_android_memory_routing(content, filename):
    if "BKA_TRANSLATE_ADDR" in content or not filename.endswith(('.c', '.h')): return content
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
    if (gN64_Reg_Base) return gN64_Reg_Base;
    static unsigned int* dummy_reg = (unsigned int*)0;
    if (!dummy_reg) dummy_reg = (unsigned int*)calloc(0x100000, 1);
    return dummy_reg;
}
static inline unsigned int* BKA_GetSafePifBase(void) {
    if (gN64_PIF_Base) return gN64_PIF_Base;
    InitN64Registers();
    if (gN64_PIF_Base) return gN64_PIF_Base;
    static unsigned int* dummy_pif = (unsigned int*)0;
    if (!dummy_pif) dummy_pif = (unsigned int*)calloc(0x1000, 1);
    return dummy_pif;
}
#endif
#define BKA_GET_REG_BASE() BKA_GetSafeRegBase()
#define BKA_GET_PIF_BASE() BKA_GetSafePifBase()
#define BKA_MASK32(a) ((unsigned long)(a) & 0xFFFFFFFF)
#define BKA_TRANSLATE_ADDR(addr) ( \\
    (BKA_MASK32(addr) >= 0x04000000 && BKA_MASK32(addr) < 0x05000000) ? ((unsigned long)BKA_GET_REG_BASE() + (BKA_MASK32(addr) - 0x04000000)) : \\
    (BKA_MASK32(addr) >= 0x1FC00000 && BKA_MASK32(addr) < 0x1FC01000) ? ((unsigned long)BKA_GET_PIF_BASE() + (BKA_MASK32(addr) - 0x1FC00000)) : \\
    (BKA_MASK32(addr) >= 0xA4000000 && BKA_MASK32(addr) < 0xA5000000) ? ((unsigned long)BKA_GET_REG_BASE() + (BKA_MASK32(addr) - 0xA4000000)) : \\
    (BKA_MASK32(addr) >= 0xBFC00000 && BKA_MASK32(addr) < 0xBFC01000) ? ((unsigned long)BKA_GET_PIF_BASE() + (BKA_MASK32(addr) - 0xBFC00000)) : \\
    (unsigned long)(addr) \\
)\n\n"""
    content = header + content
    # Only translate if line is indented (likely inside a function, avoiding global initializers)
    ptr_pat = r'^([ \t]+)\(\s*(volatile\s+[us]\d+|v?[us]\d+)\s*\*\s*\)\s*'
    content = re.sub(ptr_pat + r'(0x[0-9a-fA-F]+)', r'\1(\2 *)BKA_TRANSLATE_ADDR(\3)', content, flags=re.MULTILINE)
    content = re.sub(ptr_pat + r'(?!BKA_TRANSLATE_ADDR)([a-zA-Z0-9_]+\s*\([^)(]*\))', r'\1(\2 *)BKA_TRANSLATE_ADDR(\3)', content, flags=re.MULTILINE)
    
    content = re.sub(r'#define\s+HW_REG\s*\(\s*reg\s*,\s*type\s*\)\s*\*.*', r'#define HW_REG(reg, type) *(volatile type *)BKA_TRANSLATE_ADDR(reg)', content)
    content = re.sub(r'#define\s+IO_READ\s*\(\s*addr\s*\)\s*\*.*', r'#define IO_READ(addr) (*(vu32 *)BKA_TRANSLATE_ADDR(addr))', content)
    content = re.sub(r'#define\s+IO_WRITE\s*\(\s*addr\s*,\s*data\s*\)\s*\*.*', r'#define IO_WRITE(addr, data) (*(vu32 *)BKA_TRANSLATE_ADDR(addr) = (u32)(data))', content)
    return content

def fix_linkage_conflicts(content):
    # Restore logic from "old working file" for basic static resolution
    static_def_pattern = re.compile(r"^static\s+([\w\s\*]+\b(\w+)\s*\([^)]*\)\s*\{)", re.MULTILINE)
    for match in static_def_pattern.finditer(content):
        full_sig, func_name = match.group(1), match.group(2)
        if re.search(r"^[ \t]*(?!static\b|typedef\b)[\w\s\*]*\b" + re.escape(func_name) + r"\s*\([^)]*\)\s*;", content, re.MULTILINE):
            content = content.replace("static " + full_sig, full_sig)

    # Keep forward declaration logic for missing prototypes (essential for code_F0.c)
    sigs, added = [], set()
    clean = re.sub(r'("(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*)', ' ', content, flags=re.DOTALL)
    existing = set(re.findall(r'\b(\w+)\s*\([^;{]*\)\s*;', clean))
    for match in re.finditer(r"^[ \t]*static\s+([\w\s\*]+\b(\w+)\s*\([^;{]*\))\s*\{", content, re.MULTILINE):
        sig, name = match.group(1).strip(), match.group(2)
        if name not in existing and name not in added:
            sigs.append(f"static {sig};")
            added.add(name)
    if sigs:
        block = "\n/* Automated Forward Decls */\n" + "\n".join(sigs) + "\n\n"
        first = re.search(r"^[ \t]*(?:static\s+)?[\w\s\*]+\b\w+\s*\([^;{]*\)\s*\{", content, re.MULTILINE)
        if first: content = content[:first.start()] + block + content[first.start():]
    return content

def sanitize_codebase(root_path):
    print(f"🧹 Scanning for sanitization: {root_path}")
    include_dirs = ["include", os.path.join("include", "2.0L"), os.path.join("include", "2.0L", "PR")]
    headers_to_redirect = set()
    for ch in CONFLICTING_HEADERS:
        for sub in include_dirs:
            old, new = os.path.join(root_path, sub, ch), os.path.join(root_path, sub, f"n64_{ch}")
            if os.path.exists(old) or os.path.exists(new):
                headers_to_redirect.add(ch)
                if os.path.exists(old) and not os.path.exists(new): os.rename(old, new)

    patch_count, wrapper_count = 0, 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')): continue
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f: original_content = f.read()
                    is_wrapper = is_modern_wrapper(filepath, original_content)
                    content = original_content
                    
                    if filename not in CORE_TYPE_HEADERS:
                        content = re.sub(r'#include\s*[<"]ultratypes\.h[">]', '/* Redirected */ #include <n64_types.h>', content)
                        content = re.sub(r'#include\s*[<"]PR/ultratypes\.h[">]', '/* Redirected */ #include <n64_types.h>', content)
                    
                    if not is_wrapper:
                        tokens = [(re.compile(r"\bbool\b"), "n64_bool"), (re.compile(r"\btrue\b"), "TRUE"), (re.compile(r"\bfalse\b"), "FALSE")] if filename in CORE_TYPE_HEADERS else COMPILED_TOKENS
                        parts = re.split(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*)', content, flags=re.DOTALL)
                        for i in range(0, len(parts), 2):
                            for pat, repl in tokens: parts[i] = pat.sub(repl, parts[i])
                        content = "".join(parts)

                        # Fix decompiler artifacts (leafboat.c fix included)
                        content = re.sub(r'^([ \t]+)([a-zA-Z_]\w*)\s+([a-zA-Z_]\w*)\s*\[\s*([^\]]+)\s*\]\s*=\s*([^;{"]+)\s*;', 
                                         lambda m: f"{m.group(1)}{m.group(2)} {m.group(3)}[{m.group(4)}];\n{m.group(1)}n64_memcpy({m.group(3)}, {m.group(5).strip()}, {m.group(4)} * sizeof({m.group(2)}));", 
                                         content, flags=re.MULTILINE)

                        content = apply_android_memory_routing(content, filename)
                        if filename.endswith('.c'):
                            content = fix_linkage_conflicts(content)
                            if filename not in CORE_TYPE_HEADERS: content = inject_types_include(content, True)
                        if filename.endswith('.h') and filename not in CORE_TYPE_HEADERS:
                            if not re.search(r'#include\s*[<"](?:n64_types\.h|ultra64\.h|ultratypes\.h)[">]', content):
                                content = inject_types_include(content, False)
                    
                    if content != original_content:
                        with open(filepath, 'w', encoding='utf-8') as f: f.write(content)
                        if is_wrapper: wrapper_count += 1
                        else: patch_count += 1
                except Exception: continue
    print(f"✅ Sanitization Complete! {patch_count} core files modified. {wrapper_count} wrappers aligned.")

if __name__ == "__main__":
    sanitize_codebase(sys.argv[1] if len(sys.argv) > 1 else ".")
