import os
import re
import sys

TARGET_DIRS = ["src", "include", "lib", "libultra", "Android/app/src/main/cpp"]
CONFLICTING_HEADERS = ["string.h", "time.h", "math.h", "stdlib.h", "stdio.h", "stdarg.h", "stdint.h", "bool.h"]

TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool", r"\btrue\b": "TRUE", r"\bfalse\b": "FALSE",
    r"\bstrcat\b": "n64_strcat", r"\bstrcpy\b": "n64_strcpy", r"\bstrlen\b": "n64_strlen",
    r"\bmemcpy\b": "n64_memcpy", r"\bmemmove\b": "n64_memmove", r"\bmalloc\b": "n64_malloc",
    r"\bfree\b": "n64_free", r"\brealloc\b": "n64_realloc", r"\bcalloc\b": "n64_calloc",
    r"\bsprintf\b": "n64_sprintf", r"\bprintf\b": "n64_printf", r"\bsin\b": "n64_sin",
    r"\bcos\b": "n64_cos", r"\bvu8\b": "volatile u8", r"\bvs8\b": "volatile s8",
    r"\bvu16\b": "volatile u16", r"\bvs16\b": "volatile s16", r"\bvu32\b": "volatile u32",
    r"\bvs32\b": "volatile s32", r"\bvu64\b": "volatile u64", r"\bvs64\b": "volatile s64",
    r"\bvf32\b": "volatile f32", r"\bvf64\b": "volatile f64",
}
COMPILED_TOKENS = [(re.compile(k), v) for k, v in TOKEN_REPLACEMENTS.items()]

def apply_android_memory_routing(content, filename):
    if not filename.endswith(('.c', '.h', '.cpp', '.hpp')): return content

    header = """#ifndef BKA_SAFE_BASE_INCLUDED
#define BKA_SAFE_BASE_INCLUDED
#include <android/log.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
extern uint8_t* gN64_RDRAM;
extern uint32_t* gN64_Reg_Base;
extern uint32_t* gN64_PIF_Base;
extern void InitN64Registers(void);
#ifdef __cplusplus
}
#endif

static inline uintptr_t BKA_Validate_And_Translate(uintptr_t addr, const char* file, int line) {
    uint32_t mask32 = (uint32_t)(addr & 0xFFFFFFFF);
    if (mask32 == 0) return 0;
    if ((addr >> 32) != 0 && (addr >> 32) != 0xFFFFFFFF) return addr;
    if (!gN64_RDRAM) InitN64Registers();

    uintptr_t ram = (uintptr_t)gN64_RDRAM;
    uintptr_t reg = (uintptr_t)gN64_Reg_Base;
    uintptr_t pif = (uintptr_t)gN64_PIF_Base;

    if (mask32 < 0x01000000) return ram + mask32;
    if (mask32 >= 0x80000000 && mask32 < 0x81000000) return ram + (mask32 - 0x80000000);
    if (mask32 >= 0xA0000000 && mask32 < 0xA1000000) return ram + (mask32 - 0xA0000000);
    if (mask32 >= 0x04000000 && mask32 < 0x05000000) return reg + (mask32 - 0x04000000);
    if (mask32 >= 0xA4000000 && mask32 < 0xA5000000) return reg + (mask32 - 0xA4000000);
    if (mask32 >= 0x1FC00000 && mask32 < 0x1FC01000) return pif + (mask32 - 0x1FC00000);
    if (mask32 >= 0xBFC00000 && mask32 < 0xBFC01000) return pif + (mask32 - 0xBFC00000);

    __android_log_print(ANDROID_LOG_FATAL, "BKA_MEM_FAULT", "[%s:%d] UNMAPPED ACCESS: 0x%08x", file, line, mask32);
    return addr;
}

#define BKA_TRANSLATE_ADDR(addr) BKA_Validate_And_Translate((uintptr_t)(addr), __FILE__, __LINE__)

static inline uintptr_t BKA_Reverse_Addr(uintptr_t addr) {
    if (!gN64_RDRAM) return addr;
    uintptr_t ram = (uintptr_t)gN64_RDRAM;
    uintptr_t reg = (uintptr_t)gN64_Reg_Base;
    if (addr >= ram && addr < ram + 0x01000000) return addr - ram;
    if (addr >= reg && addr < reg + 0x01000000) return (addr - reg) + 0x04000000;
    return addr;
}
#endif\n\n"""

    # Aggressive strip of old headers
    if "BKA_SAFE_BASE_INCLUDED" in content:
        content = re.sub(r'#ifndef BKA_SAFE_BASE_INCLUDED.*?#endif\s*\n\n', '', content, flags=re.DOTALL)

    # Apply macro wrapping
    N64_PRIM_CAST = r'(?:volatile\s+)?(?:u8|s8|u16|s16|u32|s32|u64|s64|f32|f64|int|char|short|long|float|double|void)\s*\*+'
    ptr_hex_pat = re.compile(r'\(\s*(' + N64_PRIM_CAST + r')\s*\)\s*(?!BKA_TRANSLATE_ADDR\()(0x[0-9a-fA-F]+|\(\s*0x[0-9a-fA-F]+[^)]*\))')
    content = ptr_hex_pat.sub(r'(\1)BKA_TRANSLATE_ADDR(\2)', content)

    # Apply IO Redirects
    content = re.sub(r'#define\s+HW_REG\s*\(\s*reg\s*,\s*type\s*\).*', r'#define HW_REG(reg, type) (*((volatile type *)BKA_TRANSLATE_ADDR(reg)))', content)
    content = re.sub(r'#define\s+IO_READ\s*\(\s*addr\s*\).*', r'#define IO_READ(addr) (*((volatile u32 *)BKA_TRANSLATE_ADDR(addr)))', content)
    content = re.sub(r'#define\s+IO_WRITE\s*\(\s*addr\s*,\s*data\s*\).*', r'#define IO_WRITE(addr, data) (*((volatile u32 *)BKA_TRANSLATE_ADDR(addr)) = (u32)(data))', content)

    if "BKA_TRANSLATE_ADDR" in content: return header + content
    return content

def sanitize_codebase(root_path):
    print(f"🧹 Sanitizing: {root_path}")
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path): continue
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not filename.endswith(('.c', '.h', '.cpp', '.hpp')): continue
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        original = f.read()
                    content = apply_android_memory_routing(original, filename)
                    if content != original:
                        with open(filepath, 'w', encoding='utf-8') as f: f.write(content)
                except Exception: continue

if __name__ == "__main__":
    sanitize_codebase(sys.argv[1] if len(sys.argv) > 1 else ".")
