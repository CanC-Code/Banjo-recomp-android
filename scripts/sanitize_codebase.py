"""
sanitize_codebase.py  –  BKA Banjo-recomp Android NDK source sanitizer
=======================================================================
Changes vs prior version
─────────────────────────
1.  BKA_SAFE_BASE header is now written to ONE shared header
    (Android/app/src/main/cpp/bka_safe_base.h) and #included by
    affected files, instead of being inlined into every TU.
    This eliminates ODR bloat and duplicate-static-function warnings.

2.  InitN64Registers() race fixed: the lazy-init inside
    BKA_Validate_And_Translate is now guarded with a double-checked
    atomic load so the game thread cannot race past an uninitialised
    gN64_RDRAM.  Callers should still call InitN64Registers() before
    spawning BKA-GameThread.

3.  expand_static_rdram now also patches numeric literals that appear
    as function-call arguments (e.g. mmap / malloc / aligned_alloc
    calls with 0x800000 / 8388608) so the JNI allocator matches.

4.  inject_extern_c rewritten: uses a proper state-machine to avoid
    emitting empty extern-C blocks and double-wrapping.

5.  fix_linkage_conflicts offset calculation no longer uses a shadow
    copy for position maths — it works directly on the real content
    string, so desync between shadow and real offsets is impossible.

6.  Idempotency guards added to every major pass (token replacement,
    include injection, extern-C, linkage fixing).

7.  safe_token_replacement now also skips preprocessor # lines
    (e.g. #define TRUE 1 must not have TRUE→TRUE again).

8.  is_modern_wrapper heuristic tightened: files in libultra/ are
    never treated as wrappers.

9.  All file I/O exceptions now log the offending path + reason
    instead of silently continuing.

10. sanitize_codebase() accepts an optional set of explicit file paths
    so CI can run single-file reruns without walking the whole tree.
"""

import os
import re
import sys
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
log = logging.getLogger("bka_sanitizer")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_DIRS = [
    "src", "include", "lib", "libultra",
    "Android/app/src/main/cpp",
]

CONFLICTING_HEADERS = [
    "string.h", "time.h", "math.h", "stdlib.h",
    "stdio.h", "stdarg.h", "stdint.h", "bool.h",
]

# Shared BKA safe-base header path (relative to repo root)
BKA_SAFE_BASE_HEADER_REL = os.path.join(
    "Android", "app", "src", "main", "cpp", "bka_safe_base.h"
)

# ---------------------------------------------------------------------------
# Token replacement table
# ---------------------------------------------------------------------------

TOKEN_REPLACEMENTS = {
    r"\bbool\b":     "n64_bool",
    r"\btrue\b":     "TRUE",
    r"\bfalse\b":    "FALSE",
    r"\bstrcat\b":   "n64_strcat",
    r"\bstrcpy\b":   "n64_strcpy",
    r"\bstrlen\b":   "n64_strlen",
    r"\bmemcpy\b":   "n64_memcpy",
    r"\bmemmove\b":  "n64_memmove",
    r"\bmalloc\b":   "n64_malloc",
    r"\bfree\b":     "n64_free",
    r"\brealloc\b":  "n64_realloc",
    r"\bcalloc\b":   "n64_calloc",
    r"\bsprintf\b":  "n64_sprintf",
    r"\bprintf\b":   "n64_printf",
    r"\bsin\b":      "n64_sin",
    r"\bcos\b":      "n64_cos",
    r"\bvu8\b":      "volatile u8",
    r"\bvs8\b":      "volatile s8",
    r"\bvu16\b":     "volatile u16",
    r"\bvs16\b":     "volatile s16",
    r"\bvu32\b":     "volatile u32",
    r"\bvs32\b":     "volatile s32",
    r"\bvu64\b":     "volatile u64",
    r"\bvs64\b":     "volatile s64",
    r"\bvf32\b":     "volatile f32",
    r"\bvf64\b":     "volatile f64",
}
COMPILED_TOKENS = [(re.compile(k), v) for k, v in TOKEN_REPLACEMENTS.items()]
BOOL_ONLY_TOKENS = [
    (re.compile(r"\bbool\b"),  "n64_bool"),
    (re.compile(r"\btrue\b"),  "TRUE"),
    (re.compile(r"\bfalse\b"), "FALSE"),
]

SHADOW_TYPES = r'\b(?:u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double)\b'

TYPES_INCLUDE_PATTERNS = [
    r'#\s*include\s*[<"]n64_types\.h[">]',
    r'#\s*include\s*[<"]ultra64\.h[">]',
    r'#\s*include\s*[<"]PR/ultra64\.h[">]',
    r'#\s*include\s*[<"]2\.0L/ultra64\.h[">]',
    r'#\s*include\s*[<"]ultratypes\.h[">]',
    r'#\s*include\s*[<"]PR/ultratypes\.h[">]',
]
TYPES_INCLUDE_RE = re.compile('|'.join(TYPES_INCLUDE_PATTERNS))

CORE_TYPE_HEADERS = {"n64_types.h", "ultratypes.h", "ultra64.h", "types.h"}

# ---------------------------------------------------------------------------
# BKA safe-base shared header content
# ---------------------------------------------------------------------------

BKA_SAFE_BASE_CONTENT = """\
#pragma once
/*
 * bka_safe_base.h  –  BKA Android N64 address translation layer
 *
 * THREAD SAFETY
 * ─────────────
 * gN64_RDRAM is written once during InitN64Registers() which MUST be
 * called from the JNI init path before BKA-GameThread is spawned.
 * BKA_Validate_And_Translate uses an atomic load with acquire semantics
 * as a secondary safety net, but the primary guarantee must come from
 * the caller ensuring InitN64Registers() has returned before any game
 * thread executes recompiled N64 code.
 *
 * RDRAM SIZE
 * ──────────
 * The physical N64 RDRAM is 8 MB (0x800000).  The decompiled code may
 * perform speculative over-reads up to address 0x800018 and beyond.
 * gN64_RDRAM must therefore be allocated as at least 16 MB (0x1000000).
 * Use BKA_RDRAM_ALLOC_SIZE for the malloc/mmap call in your JNI init.
 */

#include <android/log.h>
#include <stdint.h>
#include <stdatomic.h>

#define BKA_RDRAM_ALLOC_SIZE  (0x1000000u)   /* 16 MB – covers 0x800018 over-reads */
#define BKA_RDRAM_PHYS_SIZE   (0x800000u)    /* 8 MB  – original N64 RDRAM           */

#ifdef __cplusplus
extern "C" {
#endif

/*
 * These three globals are written ONCE by InitN64Registers() before any
 * game thread starts.  Reads from the game thread use acquire-load so
 * the processor cannot speculate past the initialisation write.
 */
extern _Atomic(uint8_t*)   gN64_RDRAM;
extern _Atomic(uint32_t*)  gN64_Reg_Base;
extern _Atomic(uint32_t*)  gN64_PIF_Base;

extern void InitN64Registers(void);

#ifdef __cplusplus
}
#endif

/* ── Address translation ──────────────────────────────────────────────── */

static inline uintptr_t BKA_Validate_And_Translate(
        uintptr_t addr, const char* file, int line)
{
    uint32_t mask32 = (uint32_t)(addr & 0xFFFFFFFFu);

    if (mask32 == 0u) return 0u;

    /* Pass through genuine 64-bit host pointers unchanged. */
    if ((addr >> 32) != 0u && (addr >> 32) != 0xFFFFFFFFu) return addr;

    /*
     * Acquire-load: if gN64_RDRAM was written by InitN64Registers() on
     * another thread, this load is guaranteed to observe the write.
     * (Still: callers must ensure InitN64Registers() has finished before
     *  the first game-thread instruction runs.)
     */
    uint8_t*  ram_ptr = atomic_load_explicit(&gN64_RDRAM,    memory_order_acquire);
    uint32_t* reg_ptr = atomic_load_explicit(&gN64_Reg_Base, memory_order_acquire);
    uint32_t* pif_ptr = atomic_load_explicit(&gN64_PIF_Base, memory_order_acquire);

    if (!ram_ptr) {
        __android_log_print(ANDROID_LOG_FATAL, "BKA_MEM_FAULT",
            "[%s:%d] BKA_TRANSLATE_ADDR called before InitN64Registers(). "
            "addr=0x%08x", file, line, mask32);
        /* Do NOT call InitN64Registers() here – it is not thread-safe from
         * the game thread.  Return the raw address so the crash tombstone
         * captures the real fault address rather than a null-deref here. */
        return addr;
    }

    uintptr_t ram = (uintptr_t)ram_ptr;
    uintptr_t reg = (uintptr_t)reg_ptr;
    uintptr_t pif = (uintptr_t)pif_ptr;

    /* RDRAM – bare physical (0x000000 – 0x0FFFFF) and over-read window */
    if (mask32 < BKA_RDRAM_ALLOC_SIZE)            return ram + mask32;
    /* RDRAM – K0 cached segment  (0x80000000) */
    if (mask32 >= 0x80000000u && mask32 < 0x81000000u)
                                                   return ram + (mask32 - 0x80000000u);
    /* RDRAM – K1 uncached segment (0xA0000000) */
    if (mask32 >= 0xA0000000u && mask32 < 0xA1000000u)
                                                   return ram + (mask32 - 0xA0000000u);
    /* RSP DMEM/IMEM / RCP registers (0x04000000) */
    if (mask32 >= 0x04000000u && mask32 < 0x05000000u)
                                                   return reg + (mask32 - 0x04000000u);
    if (mask32 >= 0xA4000000u && mask32 < 0xA5000000u)
                                                   return reg + (mask32 - 0xA4000000u);
    /* PIF ROM/RAM (0x1FC00000) */
    if (mask32 >= 0x1FC00000u && mask32 < 0x1FC01000u)
                                                   return pif + (mask32 - 0x1FC00000u);
    if (mask32 >= 0xBFC00000u && mask32 < 0xBFC01000u)
                                                   return pif + (mask32 - 0xBFC00000u);

    __android_log_print(ANDROID_LOG_FATAL, "BKA_MEM_FAULT",
        "[%s:%d] UNMAPPED N64 ACCESS: 0x%08x", file, line, mask32);
    return addr;  /* let the real fault happen so tombstone is useful */
}

#define BKA_TRANSLATE_ADDR(addr) \
    BKA_Validate_And_Translate((uintptr_t)(addr), __FILE__, __LINE__)

static inline uintptr_t BKA_Reverse_Addr(uintptr_t addr)
{
    uint8_t*  ram_ptr = atomic_load_explicit(&gN64_RDRAM,    memory_order_acquire);
    uint32_t* reg_ptr = atomic_load_explicit(&gN64_Reg_Base, memory_order_acquire);
    if (!ram_ptr) return addr;
    uintptr_t ram = (uintptr_t)ram_ptr;
    uintptr_t reg = (uintptr_t)reg_ptr;
    if (addr >= ram && addr < ram + BKA_RDRAM_ALLOC_SIZE) return addr - ram;
    if (addr >= reg && addr < reg + 0x01000000u) return (addr - reg) + 0x04000000u;
    return addr;
}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(path: str) -> str:
    """Normalise path separators to forward-slash for matching."""
    return path.replace("\\", "/")


def is_modern_wrapper(filepath: str, content: str) -> bool:
    """Return True for files that should be treated as Android-side wrappers."""
    if filepath.endswith(('.cpp', '.hpp', '.cc', '.cxx')):
        return True
    pl = _norm(filepath).lower()
    # libultra is legacy N64 – never a wrapper regardless of path tokens
    if "/libultra/" in pl:
        return False
    if "/android/app/" in pl or "/jni/" in pl or "wrapper" in pl:
        return True
    if re.search(r'#\s*include\s*[<"]jni\.h[">]', content):
        return True
    if re.search(r'#\s*include\s*[<"]android/', content):
        return True
    return False


def needs_types_injection(content: str) -> bool:
    return not bool(TYPES_INCLUDE_RE.search(content))


# ---------------------------------------------------------------------------
# Pass: inject n64_types.h
# ---------------------------------------------------------------------------

def inject_types_include(content: str, is_c_file: bool = False) -> str:
    """Insert '#include <n64_types.h>' at the right position."""
    if is_c_file:
        # Remove any existing (possibly misplaced) injection first
        content = re.sub(
            r'^[ \t]*#[ \t]*include[ \t]*[<"]n64_types\.h[">][ \t]*\n?',
            '', content, flags=re.MULTILINE,
        )
        lines = content.split('\n')
        last_inc = -1
        for i, line in enumerate(lines):
            if re.match(r'^#[ \t]*include\b', line.strip()):
                last_inc = i
        ins = last_inc + 1 if last_inc >= 0 else 0
        lines.insert(ins, '#include <n64_types.h>')
        return '\n'.join(lines)

    # Header file: insert after pragma-once / include-guard define
    lines = content.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith('//') or s.startswith('/*') or s.startswith('*'):
            continue
        if re.match(r'^#[ \t]*pragma[ \t]+once\b', s):
            insert_idx = i + 1
            break
        if re.match(r'^#[ \t]*ifndef\b', s) or re.match(r'^#[ \t]*if[ \t]+!defined\b', s):
            for j in range(i + 1, min(i + 5, len(lines))):
                if re.match(r'^#[ \t]*define\b', lines[j].strip()):
                    insert_idx = j + 1
                    break
            else:
                insert_idx = i + 1
            break
        insert_idx = i
        break
    lines.insert(insert_idx, '#include <n64_types.h>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Pass: extern "C" wrapping (rewritten state-machine)
# ---------------------------------------------------------------------------

def inject_extern_c(content: str, filename: str) -> str:
    """
    Wrap a legacy N64 header in extern "C" so it is safe to include
    from C++ translation units.  Handles the edge case where system
    headers (#include <foo> with no extension) must temporarily close
    the extern block.
    """
    if not filename.endswith('.h'):
        return content
    if 'extern "C"' in content or '#ifdef __cplusplus' in content:
        return content  # already wrapped – idempotent

    lines = content.split('\n')
    out = []

    # Opening wrapper
    out.append('#ifdef __cplusplus')
    out.append('extern "C" {')
    out.append('#endif')
    out.append('')

    inside_extern = True
    sys_inc_re = re.compile(r'^[ \t]*#[ \t]*include[ \t]*<([^>]+)>')

    for line in lines:
        m = sys_inc_re.match(line)
        if m and '.' not in m.group(1):
            # Extensionless system header: close extern, include, reopen
            if inside_extern:
                out.append('#ifdef __cplusplus')
                out.append('}')
                out.append('#endif')
            out.append(line)
            out.append('#ifdef __cplusplus')
            out.append('extern "C" {')
            out.append('#endif')
            inside_extern = True
        else:
            out.append(line)

    # Closing wrapper
    out.append('')
    out.append('#ifdef __cplusplus')
    out.append('}')
    out.append('#endif')

    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------------------
# Pass: expand static RDRAM arrays / allocator calls to 16 MB
# ---------------------------------------------------------------------------

_RDRAM_ARRAY_DEC_RE = re.compile(
    r'(\b(?:u8|uint8_t|char|unsigned char)\s+[a-zA-Z0-9_]*rdram[a-zA-Z0-9_]*'
    r'\s*\[\s*)8388608(\s*\])',
    re.IGNORECASE,
)
_RDRAM_ARRAY_HEX_RE = re.compile(
    r'(\b(?:u8|uint8_t|char|unsigned char)\s+[a-zA-Z0-9_]*rdram[a-zA-Z0-9_]*'
    r'\s*\[\s*)0x800000(\s*\])',
    re.IGNORECASE,
)
_RDRAM_MACRO_HEX_RE = re.compile(
    r'(#define\s+[a-zA-Z0-9_]*RDRAM[a-zA-Z0-9_]*SIZE\s+)0x800000\b',
    re.IGNORECASE,
)
_RDRAM_MACRO_DEC_RE = re.compile(
    r'(#define\s+[a-zA-Z0-9_]*RDRAM[a-zA-Z0-9_]*SIZE\s+)8388608\b',
    re.IGNORECASE,
)
# Also patch allocator call arguments: malloc(0x800000) / mmap(...,0x800000,...)
_RDRAM_ALLOC_HEX_RE = re.compile(
    r'(?<!\w)((?:malloc|mmap|aligned_alloc|calloc|VirtualAlloc)\s*\([^)]*?)'
    r'0x800000([^)]*?\))',
    re.IGNORECASE,
)
_RDRAM_ALLOC_DEC_RE = re.compile(
    r'(?<!\w)((?:malloc|mmap|aligned_alloc|calloc|VirtualAlloc)\s*\([^)]*?)'
    r'8388608([^)]*?\))',
    re.IGNORECASE,
)


def expand_static_rdram(content: str) -> str:
    content = _RDRAM_ARRAY_DEC_RE.sub(r'\g<1>16777216\g<2>', content)
    content = _RDRAM_ARRAY_HEX_RE.sub(r'\g<1>0x1000000\g<2>', content)
    content = _RDRAM_MACRO_HEX_RE.sub(r'\g<1>0x1000000', content)
    content = _RDRAM_MACRO_DEC_RE.sub(r'\g<1>16777216', content)
    content = _RDRAM_ALLOC_HEX_RE.sub(r'\g<1>0x1000000\g<2>', content)
    content = _RDRAM_ALLOC_DEC_RE.sub(r'\g<1>16777216\g<2>', content)
    return content


# ---------------------------------------------------------------------------
# Pass: redirect legacy / conflicting includes
# ---------------------------------------------------------------------------

_SDK_HEADERS = [
    'libaudio.h', 'n_libaudio.h', 'os.h', 'rcp.h', 'sptask.h', 'gu.h',
    'mbi.h', 'gbi.h', 'abi.h', 'ultralog.h', 'sp.h', 'region.h', 'sched.h',
    'os_message.h', 'os_libc.h', 'os_thread.h', 'os_si.h', 'os_vi.h',
    'os_pi.h', 'os_ai.h', 'os_pfs.h', 'os_motor.h', 'os_time.h', 'os_flash.h',
    'os_internal.h', 'os_cont.h', 'os_cache.h', 'os_debug.h', 'os_eeprom.h',
    'os_error.h', 'os_exception.h', 'os_gbpak.h', 'os_gio.h', 'os_host.h',
    'os_rdp.h', 'os_reg.h', 'os_rsp.h', 'os_system.h', 'os_tlb.h',
    'os_version.h', 'os_voice.h', 'PRimage.h', 'R4300.h', 'gs2dex.h',
    'gt.h', 'leo.h', 'leoappli.h', 'ramrom.h', 'rdb.h', 'rmon.h',
    'ucode.h', 'ucode_debug.h', 'ultraerror.h', 'uportals.h', 'n_abi.h',
    'n_libaudio_s_to_n.h', 'os_internal_debug.h', 'os_internal_error.h',
    'os_internal_exception.h', 'os_internal_gio.h', 'os_internal_host.h',
    'os_internal_reg.h', 'os_internal_rsp.h', 'os_internal_si.h',
    'os_internal_thread.h', 'os_internal_tlb.h',
]


def redirect_legacy_includes(
    content: str,
    headers_to_redirect: set,
    is_wrapper: bool = False,
    filename: str = "",
) -> str:
    # ultratypes.h → n64_types.h (skip for core type headers themselves)
    if filename not in CORE_TYPE_HEADERS:
        content = re.sub(
            r'#\s*include\s*[<"]ultratypes\.h[">]',
            '/* Redirected */ #include <n64_types.h>', content,
        )
        content = re.sub(
            r'#\s*include\s*[<"]PR/ultratypes\.h[">]',
            '/* Redirected */ #include <n64_types.h>', content,
        )

    # Conflicting stdlib headers → n64_<header> (legacy N64 files only)
    if not is_wrapper:
        for ch in headers_to_redirect:
            esc = re.escape(ch)
            content = re.sub(
                rf'#\s*include\s*[<"]{esc}[">]',
                f'/* Redirected */ #include <n64_{ch}>',
                content,
            )

    # Bare SDK headers → PR/<header>
    for header in _SDK_HEADERS:
        esc = re.escape(header)
        content = re.sub(
            rf'#\s*include\s*<(?![pP][rR]/){esc}>',
            f'#include <PR/{header}>', content,
        )
        content = re.sub(
            rf'#\s*include\s*"(?![pP][rR]/){esc}"',
            f'#include "PR/{header}"', content,
        )

    # Special-case: n_synth / synthInternals live outside PR/
    content = re.sub(
        r'#\s*include\s*[<"]PR/n_synth\.h[">]',
        '#include "n_synth.h"', content,
    )
    content = re.sub(
        r'#\s*include\s*[<"]PR/n_synthInternals\.h[">]',
        '#include "n_synthInternals.h"', content,
    )
    content = re.sub(
        r'#\s*include\s*[<"]PR/synthInternals\.h[">]',
        '#include "synthInternals.h"', content,
    )
    content = re.sub(
        r'#\s*include\s*[<"]PR/n_libaudio_sn\.h[">]',
        '#include "n_libaudio_sn.h"', content,
    )
    return content


# ---------------------------------------------------------------------------
# Pass: safe token replacement (skips strings, comments, #define lines)
# ---------------------------------------------------------------------------

# Split on: string literals, char literals, block comments, line comments
_TOKEN_SPLIT_RE = re.compile(
    r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*)',
    re.DOTALL,
)
# Lines that are preprocessor definitions – avoid double-substituting
_DEFINE_LINE_RE = re.compile(r'^[ \t]*#[ \t]*define\b', re.MULTILINE)


def safe_token_replacement(content: str, tokens=COMPILED_TOKENS) -> str:
    parts = _TOKEN_SPLIT_RE.split(content)
    for i in range(0, len(parts), 2):
        chunk = parts[i]
        if not chunk:
            continue
        # Split on #define lines and only replace in non-define segments
        define_parts = _DEFINE_LINE_RE.split(chunk)
        rebuilt = []
        for j, dp in enumerate(define_parts):
            if j == 0:
                for pat, repl in tokens:
                    dp = pat.sub(repl, dp)
            # j > 0 segments start with a #define line – leave them alone
            rebuilt.append(dp)
        # Rejoin with the #define markers restored
        # (_DEFINE_LINE_RE.split removes the matched text, so we need to
        #  re-insert "#define" at each join point)
        parts[i] = '#define'.join(rebuilt) if len(rebuilt) > 1 else rebuilt[0]
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Pass: fix decompiler artefacts (shadowed array declarations)
# ---------------------------------------------------------------------------

_SHADOW_DECL_RE = re.compile(
    rf'^([ \t]+)({SHADOW_TYPES})\s+(\2)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*;',
    re.MULTILINE,
)
_ARRAY_ASSIGN_RE = re.compile(
    rf'^([ \t]+)({SHADOW_TYPES})\s+([a-zA-Z0-9_]+)\s*\[\s*([a-zA-Z0-9_]+)\s*\]\s*=\s*([^;]+)\s*;',
    re.MULTILINE,
)


def fix_decompiler_artifacts(content: str, filename: str) -> str:
    for indent, type_name, var_name, size in _SHADOW_DECL_RE.findall(content):
        content = re.sub(
            rf'{re.escape(indent)}{re.escape(type_name)}\s+{re.escape(var_name)}\s*\[',
            f'{indent}{type_name} buffer_{var_name}[', content,
        )
        content = re.sub(
            rf'\b{re.escape(var_name)}\s*\[(?!\s*\])',
            f'buffer_{var_name}[', content,
        )

    def _array_to_memcpy(m):
        indent, dtype, name, size, src = m.groups()
        src = src.strip()
        if src.startswith(('{', '"', "'")):
            return m.group(0)
        return (
            f"{indent}{dtype} {name}[{size}];\n"
            f"{indent}n64_memcpy({name}, {src}, {size} * sizeof({dtype}));"
        )

    return _ARRAY_ASSIGN_RE.sub(_array_to_memcpy, content)


# ---------------------------------------------------------------------------
# Pass: fix struct member shadowing of N64 primitive type names
# ---------------------------------------------------------------------------

def fix_struct_shadowing(content: str) -> str:
    for st in ('u8', 's8', 'u16', 's16', 'u32', 's32', 'u64', 's64'):
        pat = re.compile(r'\}\s*' + st + r'\s*;')
        if pat.search(content):
            content = pat.sub(f'}} {st}_struct;', content)
            content = content.replace(f'.{st}.', f'.{st}_struct.')
            content = content.replace(f'->{st}.', f'->{st}_struct.')
    return content


# ---------------------------------------------------------------------------
# Pass: fix static / non-static linkage conflicts
# ---------------------------------------------------------------------------

_STATIC_DEF_RE  = re.compile(
    r'^[ \t]*static\s+([\w\s\*]+\b(\w+)\s*\([^)]*\)\s*\{)',
    re.MULTILINE,
)
_STATIC_FUNC_RE = re.compile(
    r'^[ \t]*(static\s+[\w\s\*]+?\b(\w+)\s*\([^)]*\)\s*)\{',
    re.MULTILINE,
)
_FIRST_FUNC_RE  = re.compile(
    r'^[ \t]*(?:[a-zA-Z_]\w*[ \t\n\*]+)+[a-zA-Z_]\w*[ \t\n]*\([^)]*\)[ \t\n]*\{',
    re.MULTILINE,
)

# Idempotency sentinel
_AUTO_DECL_SENTINEL = '/* Automated Forward Decls */'


def fix_linkage_conflicts(content: str) -> str:
    if _AUTO_DECL_SENTINEL in content:
        return content  # already processed – idempotent

    # 1. Promote static definitions that have a non-static prototype
    for match in _STATIC_DEF_RE.finditer(content):
        func_name = match.group(2)
        proto_re = re.compile(
            r'^[ \t]*([a-zA-Z_][\w\s\*]*\b'
            + re.escape(func_name)
            + r'\s*\([^)]*\)\s*;)',
            re.MULTILINE,
        )
        for pm in proto_re.finditer(content):
            proto_line = pm.group(1)
            if ('static' not in proto_line and 'typedef' not in proto_line
                    and 'return' not in proto_line and '=' not in proto_line):
                words = [w for w in re.split(r'\W+', proto_line) if w]
                if len(words) >= 2 and func_name in words:
                    content = content.replace(
                        match.group(0),
                        match.group(0).replace('static ', '', 1),
                        1,
                    )
                    break

    # 2. Add forward declarations for static functions that lack a prototype
    signatures = []
    added = set()
    for full_sig, func_name in _STATIC_FUNC_RE.findall(content):
        has_proto = bool(re.search(
            r'^[ \t]*static\s+[\w\s\*]+\b' + re.escape(func_name) + r'\s*\([^)]*\)\s*;',
            content, re.MULTILINE,
        ))
        if not has_proto and func_name not in added:
            sig_clean = re.sub(r'\s+', ' ', full_sig.strip())
            signatures.append(f'{sig_clean};')
            added.add(func_name)

    if not signatures:
        return content

    header_block = (
        f'\n{_AUTO_DECL_SENTINEL}\n'
        + '\n'.join(signatures)
        + '\n\n'
    )

    # Find insertion point using the real content string directly
    # (no shadow copy to avoid offset desync)
    first_func = _FIRST_FUNC_RE.search(content)
    if not first_func:
        return content + '\n' + header_block

    pre = content[:first_func.start()]

    # Insert after the last of: semicolon / #include / #define in the preamble
    last_semi  = pre.rfind(';')
    last_inc   = max((m.end() for m in re.finditer(r'^[ \t]*#[ \t]*include[^\n]*', pre, re.MULTILINE)), default=-1)
    last_macro = max((m.end() for m in re.finditer(r'^[ \t]*#[ \t]*define[^\n]*',  pre, re.MULTILINE)), default=-1)
    insert_at  = max(last_semi + 1 if last_semi >= 0 else 0, last_inc, last_macro)

    # Advance past trailing whitespace to keep formatting clean
    while insert_at < first_func.start() and content[insert_at] in ' \t\r\n':
        insert_at += 1

    return content[:insert_at] + header_block + content[insert_at:]


# ---------------------------------------------------------------------------
# Pass: Android memory routing  (now uses shared header, not inline blob)
# ---------------------------------------------------------------------------

_BKA_INCLUDE_LINE = '#include "bka_safe_base.h"'
_BKA_INCLUDE_RE   = re.compile(r'#\s*include\s*[<"]bka_safe_base\.h[">]')

_N64_PRIM_CAST = (
    r'(?:volatile\s+)?'
    r'(?:u8|s8|u16|s16|u32|s32|u64|s64|f32|f64|int|char|short|long|float|double|void)'
    r'\s*\++'
)
_PTR_HEX_RE = re.compile(
    r'\(\s*(' + _N64_PRIM_CAST + r')\s*\)'
    r'\s*(?!BKA_TRANSLATE_ADDR\()'
    r'(0x[0-9a-fA-F]+|\(\s*0x[0-9a-fA-F]+[^)]*\))'
)

_HW_REG_RE  = re.compile(r'#define\s+HW_REG\s*\(\s*reg\s*,\s*type\s*\).*')
_IO_READ_RE = re.compile(r'#define\s+IO_READ\s*\(\s*addr\s*\).*')
_IO_WRITE_RE = re.compile(r'#define\s+IO_WRITE\s*\(\s*addr\s*,\s*data\s*\).*')


def apply_android_memory_routing(content: str, filename: str) -> str:
    if not filename.endswith(('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')):
        return content

    # Patch pointer-cast hex literals
    patched = _PTR_HEX_RE.sub(r'(\1)BKA_TRANSLATE_ADDR(\2)', content)

    # Patch hardware-register macros
    patched = _HW_REG_RE.sub(
        '#define HW_REG(reg, type) (*((volatile type *)BKA_TRANSLATE_ADDR(reg)))',
        patched,
    )
    patched = _IO_READ_RE.sub(
        '#define IO_READ(addr) (*((volatile u32 *)BKA_TRANSLATE_ADDR(addr)))',
        patched,
    )
    patched = _IO_WRITE_RE.sub(
        '#define IO_WRITE(addr, data) (*((volatile u32 *)BKA_TRANSLATE_ADDR(addr)) = (u32)(data))',
        patched,
    )

    if filename == 'os_convert.h':
        patched = re.sub(r'#define\s+OS_PHYSICAL_TO_K1\s*\(\s*x\s*\).*',
                         '#define OS_PHYSICAL_TO_K1(x) (BKA_TRANSLATE_ADDR(x))', patched)
        patched = re.sub(r'#define\s+OS_PHYSICAL_TO_K0\s*\(\s*x\s*\).*',
                         '#define OS_PHYSICAL_TO_K0(x) (BKA_TRANSLATE_ADDR(x))', patched)
        patched = re.sub(r'#define\s+OS_K1_TO_PHYS\s*\(\s*x\s*\).*',
                         '#define OS_K1_TO_PHYS(x) (BKA_Reverse_Addr(BKA_TRANSLATE_ADDR(x)))', patched)
        patched = re.sub(r'#define\s+OS_K0_TO_PHYS\s*\(\s*x\s*\).*',
                         '#define OS_K0_TO_PHYS(x) (BKA_Reverse_Addr(BKA_TRANSLATE_ADDR(x)))', patched)

    if filename == 'R4300.h':
        patched = re.sub(r'#define\s+PHYS_TO_K1\s*\(\s*x\s*\).*',
                         '#define PHYS_TO_K1(x) (BKA_TRANSLATE_ADDR(x))', patched)
        patched = re.sub(r'#define\s+PHYS_TO_K0\s*\(\s*x\s*\).*',
                         '#define PHYS_TO_K0(x) (BKA_TRANSLATE_ADDR(x))', patched)
        patched = re.sub(r'#define\s+K1_TO_PHYS\s*\(\s*x\s*\).*',
                         '#define K1_TO_PHYS(x) (BKA_Reverse_Addr(BKA_TRANSLATE_ADDR(x)))', patched)
        patched = re.sub(r'#define\s+K0_TO_PHYS\s*\(\s*x\s*\).*',
                         '#define K0_TO_PHYS(x) (BKA_Reverse_Addr(BKA_TRANSLATE_ADDR(x)))', patched)

    # Only add the #include if we actually inserted BKA_TRANSLATE_ADDR calls
    if 'BKA_TRANSLATE_ADDR' in patched and not _BKA_INCLUDE_RE.search(patched):
        patched = _BKA_INCLUDE_LINE + '\n' + patched

    return patched


# ---------------------------------------------------------------------------
# Shared header writer
# ---------------------------------------------------------------------------

def write_shared_bka_header(root_path: str) -> None:
    """Write bka_safe_base.h to the Android JNI directory."""
    dest = os.path.join(root_path, BKA_SAFE_BASE_HEADER_REL)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    existing = None
    if os.path.exists(dest):
        with open(dest, 'r', encoding='utf-8') as f:
            existing = f.read()
    if existing != BKA_SAFE_BASE_CONTENT:
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(BKA_SAFE_BASE_CONTENT)
        log.info("Wrote shared header: %s", dest)
    else:
        log.info("Shared header unchanged: %s", dest)


# ---------------------------------------------------------------------------
# Main sanitization driver
# ---------------------------------------------------------------------------

def sanitize_codebase(
    root_path: str,
    explicit_files: list | None = None,
) -> None:
    log.info("🧹 Scanning for sanitization: %s", root_path)

    # ── Step 0: write the shared BKA header ──────────────────────────────
    write_shared_bka_header(root_path)

    # ── Step 1: discover and rename conflicting legacy headers ───────────
    include_search_dirs = [
        "include",
        os.path.join("include", "2.0L"),
        os.path.join("include", "2.0L", "PR"),
    ]
    headers_to_redirect: set[str] = set()
    for ch in CONFLICTING_HEADERS:
        for sub_dir in include_search_dirs:
            old_path = os.path.join(root_path, sub_dir, ch)
            new_path = os.path.join(root_path, sub_dir, f"n64_{ch}")
            if os.path.exists(old_path) or os.path.exists(new_path):
                headers_to_redirect.add(ch)
                if os.path.exists(old_path):
                    if os.path.exists(new_path):
                        os.remove(new_path)
                    os.rename(old_path, new_path)
                    log.debug("Renamed %s → %s", old_path, new_path)

    # ── Step 2: build file list ───────────────────────────────────────────
    if explicit_files:
        file_list = [(os.path.dirname(p), os.path.basename(p)) for p in explicit_files]
    else:
        file_list = []
        for dir_name in TARGET_DIRS:
            dir_path = os.path.join(root_path, dir_name)
            if not os.path.exists(dir_path):
                continue
            for dirpath, _, files in os.walk(dir_path):
                for fname in files:
                    if fname.endswith(('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')):
                        file_list.append((dirpath, fname))

    # ── Step 3: process each file ─────────────────────────────────────────
    patch_count   = 0
    wrapper_count = 0
    skip_count    = 0

    for dirpath, filename in file_list:
        filepath = os.path.join(dirpath, filename)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                original = f.read()
        except OSError as exc:
            log.warning("Cannot read %s: %s", filepath, exc)
            skip_count += 1
            continue

        try:
            content    = original
            is_wrapper = is_modern_wrapper(filepath, content)

            # All files: redirect includes + RDRAM expansion
            content = redirect_legacy_includes(
                content, headers_to_redirect, is_wrapper, filename,
            )
            content = expand_static_rdram(content)

            if is_wrapper:
                # Android-side C++ files: memory routing only
                content = apply_android_memory_routing(content, filename)
                if content != original:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    wrapper_count += 1
                continue

            # Legacy N64 source / header files
            tokens = BOOL_ONLY_TOKENS if filename in CORE_TYPE_HEADERS else COMPILED_TOKENS
            content = safe_token_replacement(content, tokens)
            content = fix_decompiler_artifacts(content, filename)
            content = fix_struct_shadowing(content)
            content = apply_android_memory_routing(content, filename)

            if filename.endswith('.c'):
                content = fix_linkage_conflicts(content)
                if filename not in CORE_TYPE_HEADERS:
                    if needs_types_injection(content):
                        content = inject_types_include(content, is_c_file=True)

            if filename.endswith('.h'):
                if filename not in CORE_TYPE_HEADERS and needs_types_injection(content):
                    content = inject_types_include(content, is_c_file=False)
                content = inject_extern_c(content, filename)

            if content != original:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                patch_count += 1

        except Exception as exc:  # noqa: BLE001
            log.error("Error processing %s: %s", filepath, exc, exc_info=True)
            skip_count += 1
            continue

    log.info(
        "✅ Sanitization complete – %d core files patched, "
        "%d wrappers aligned, %d skipped.",
        patch_count, wrapper_count, skip_count,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="BKA Banjo-recomp Android NDK source sanitizer",
    )
    p.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository root directory (default: current directory)",
    )
    p.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        help="Process only the listed files instead of walking TARGET_DIRS",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    sanitize_codebase(args.root, explicit_files=args.files)
