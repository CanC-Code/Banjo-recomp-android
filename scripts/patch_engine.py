import os
import re
import logging
import sys
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional, Union

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
try:
    from error_parser import (
        BRACE_MATCH, N64_STRUCT_BODIES as _EP_STRUCTS, KNOWN_MACROS as _EP_MACROS,
        KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES,
        read_file as _ep_read, write_file as _ep_write,
    )
    read_file  = _ep_read
    write_file = _ep_write
except ImportError:
    BRACE_MATCH = r"[^{}]*"
    _EP_STRUCTS = {}
    _EP_MACROS  = {}

    def read_file(filepath: str) -> str:
        try:
            with open(filepath, 'r', errors='replace') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return ""

    def write_file(filepath: str, content: str) -> None:
        try:
            with open(filepath, 'w') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write {filepath}: {e}")

    KNOWN_FUNCTION_MACROS = {}
    POSIX_RESERVED_NAMES = {
        "close", "open", "read", "write", "send", "recv",
        "connect", "accept", "bind", "listen", "select",
        "poll", "dup", "dup2", "fork", "exec", "exit",
        "stat", "fstat", "lstat", "access", "unlink", "rename",
        "mkdir", "rmdir", "chdir", "getcwd",
        "getpid", "getppid", "getuid", "getgid",
        "signal", "raise", "kill",
        "printf", "fprintf", "sprintf", "snprintf",
        "scanf", "fscanf", "sscanf",
        "time", "clock", "sleep", "usleep",
        "malloc", "calloc", "realloc", "free",
        "memcpy", "memset", "memmove", "memcmp",
        "strlen", "strcpy", "strncpy", "strcmp", "strncmp",
        "strcat", "strncat", "strchr", "strrchr", "strstr",
        "atoi", "atol", "atof", "strtol", "strtod",
        "abs", "labs", "fabs", "sqrt", "pow",
        "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
        "rand", "srand",
    }

# ---------------------------------------------------------------------------
# Phase macro tables
# ---------------------------------------------------------------------------
PHASE_1_MACROS = {
    "OS_IM_NONE": "0x0000",
    "OS_IM_1": "0x0001", "OS_IM_2": "0x0002",
    "OS_IM_3": "0x0004", "OS_IM_4": "0x0008",
    "OS_IM_5": "0x0010", "OS_IM_6": "0x0020",
    "OS_IM_7": "0x0040", "OS_IM_ALL": "0x007F",
    "PFS_ERR_ID_FATAL": "0x10",
    "PFS_ERR_DEVICE":   "0x02",
    "PFS_ERR_CONTRFAIL":"0x01",
    "PFS_ERR_INVALID":  "0x03",
    "PFS_ERR_EXIST":    "0x04",
    "PFS_ERR_NOEXIST":  "0x05",
    "PFS_DATA_ENXIO":   "0x06",
    "ADPCMFSIZE": "9",
    "ADPCMVSIZE": "16",
    "UNITY_PITCH": "0x8000",
    "MAX_RATIO":   "0xFFFF",
    "PI_DOMAIN1":  "0",
    "PI_DOMAIN2":  "1",
}

PHASE_2_MACROS = {
    **PHASE_1_MACROS,
    "DEVICE_TYPE_64DD": "0x06",
    "LEO_CMD_TYPE_0": "0", "LEO_CMD_TYPE_1": "1", "LEO_CMD_TYPE_2": "2",
    "LEO_SECTOR_MODE": "1", "LEO_TRACK_MODE": "2",
    "LEO_BM_CTL": "0x05000510", "LEO_BM_CTL_RESET": "0",
    "LEO_ERROR_29": "29", "OS_READ": "0", "OS_WRITE": "1",
    "OS_MESG_NOBLOCK": "0", "OS_MESG_BLOCK": "1",
    "PI_STATUS_REG":        "0x04600010",
    "PI_DRAM_ADDR_REG":     "0x04600000",
    "PI_CART_ADDR_REG":     "0x04600004",
    "PI_RD_LEN_REG":        "0x04600008",
    "PI_WR_LEN_REG":        "0x0460000C",
    "PI_STATUS_DMA_BUSY":   "0x01",
    "PI_STATUS_IO_BUSY":    "0x02",
    "PI_STATUS_ERROR":      "0x04",
    "PI_STATUS_INTERRUPT":  "0x08",
    "PI_BSD_DOM1_LAT_REG":  "0x04600014",
    "PI_BSD_DOM1_PWD_REG":  "0x04600018",
    "PI_BSD_DOM1_PGS_REG":  "0x0460001C",
    "PI_BSD_DOM1_RLS_REG":  "0x04600020",
    "PI_BSD_DOM2_LAT_REG":  "0x04600024",
    "PI_BSD_DOM2_PWD_REG":  "0x04600028",
    "PI_BSD_DOM2_PGS_REG":  "0x0460002C",
    "PI_BSD_DOM2_RLS_REG":  "0x04600030",
}

PHASE_3_MACROS = {
    **PHASE_2_MACROS,
    "G_ON": "1", "G_OFF": "0",
    "G_RM_AA_ZB_OPA_SURF":  "0x00000000",
    "G_RM_AA_ZB_OPA_SURF2": "0x00000000",
    "G_RM_AA_ZB_XLU_SURF":  "0x00000000",
    "G_RM_AA_ZB_XLU_SURF2": "0x00000000",
    "G_ZBUFFER": "0x00000001", "G_SHADE": "0x00000004",
    "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
}

# ---------------------------------------------------------------------------
# N64 struct bodies — TOPOLOGICALLY SORTED (dependencies before dependents)
# NOTE: OSTask and OSScTask are intentionally OMITTED because the SDK headers
# define them as unions — injecting struct versions causes redefinition errors.
#
# FIX: OSThread's 'context' field is now a proper __OSThreadContext struct
# with a 'status' member, matching the N64 SDK __OSThreadContext layout.
# exceptasm.cpp accesses __osRunningThread->context.status which requires this.
# ---------------------------------------------------------------------------
_N64_OS_STRUCT_BODIES = {
    "Mtx": """\
typedef union {
    struct { float mf[4][4]; } f;
    struct { s16   mi[4][4]; s16 pad; } i;
} Mtx;""",
    "OSContStatus": "typedef struct OSContStatus_s { u16 type; u8 status; u8 errno; } OSContStatus;",
    "OSContPad":    "typedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; u8 errno; } OSContPad;",
    "OSMesgQueue":  "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; s32 validCount; s32 first; s32 msgCount; OSMesg *msg; } OSMesgQueue;",
    # FIX: OSThread.context is now __OSThreadContext (a struct with status/cause/epc/badvaddr
    # and the full register file) instead of a raw long long array.  exceptasm.cpp
    # accesses __osRunningThread->context.status so the field must exist.
    "OSThread": """\
#ifndef __OSThreadContext_DEFINED
#define __OSThreadContext_DEFINED
typedef struct __OSThreadContext_s {
    u64 at, v0, v1, a0, a1, a2, a3;
    u64 t0, t1, t2, t3, t4, t5, t6, t7;
    u64 s0, s1, s2, s3, s4, s5, s6, s7;
    u64 t8, t9, gp, sp, s8, ra;
    u64 lo, hi;
    u32 sr, pc, cause, badvaddr;
    u32 rcp;
    u32 fpcsr;
    u32 status;  /* SR at exception time — used by exceptasm.cpp */
    f64 fp0,  fp2,  fp4,  fp6,  fp8,  fp10, fp12, fp14;
    f64 fp16, fp18, fp20, fp22, fp24, fp26, fp28, fp30;
} __OSThreadContext;
#endif
typedef struct OSThread_s {
    struct OSThread_s  *next;
    OSPri               priority;
    struct OSThread_s **queue;
    struct OSThread_s  *tlnext;
    u16                 state;
    u16                 flags;
    OSId                id;
    int                 fp;
    __OSThreadContext   context;
} OSThread;""",
    "OSMesgHdr":    "typedef struct { u16 type; u8 pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
    "OSPiHandle": """\
#ifndef __OSBlockInfo_DEFINED
#define __OSBlockInfo_DEFINED
typedef struct { u32 errStatus; void *dramAddr; void *C2Addr; u32 sectorSize; u32 C1ErrNum; u32 C1ErrSector[4]; } __OSBlockInfo;
#endif
#ifndef __OSTranxInfo_DEFINED
#define __OSTranxInfo_DEFINED
typedef struct { u32 cmdType; u16 transferMode; u16 blockNum; s32 sectorNum; u32 devAddr; u32 bmCtlShadow; u32 seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;
#endif
typedef struct OSPiHandle_s { struct OSPiHandle_s *next; u8 type; u8 latency; u8 pageSize; u8 relDuration; u8 pulse; u8 domain; u32 baseAddress; u32 speed; __OSTranxInfo transferInfo; } OSPiHandle;""",
    "OSIoMesg":  "typedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; u32 devAddr; u32 size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
    "OSDevMgr":  "typedef struct OSDevMgr_s { s32 active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; s32 (*dma)(s32, u32, void *, u32); s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32); } OSDevMgr;",
    "OSPfs": """\
typedef struct OSPfs_s {
    struct OSIoMesg_s    ioMesgBuf;
    struct OSMesgQueue_s *queue;
    s32         channel;
    u8          activebank;
    u8          banks;
    u8          inodeTable[256];
    u8          dir[256];
    u32         label[8];
    s32         repairList[256];
    u32         version;
    u32         checksum;
    u32         inodeCacheIndex;
    u8          inodeCache[256];
} OSPfs;""",
    "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;",
    "LookAt":  "typedef struct { struct { float x, y, z; float pad; } l[2]; } LookAt;",
}

# Structs the SDK already defines — we must NOT inject our own version.
# OSTask is a union in the SDK headers; OSScTask depends on it.
SDK_DEFINES_THESE = {"OSTask", "OSScTask"}

PHASE_3_STRUCTS = {
    "Gfx": "typedef struct { u32 words[2]; } Gfx;",
    "Vtx": "typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t; typedef union { Vtx_t v; long long int force_align[8]; } Vtx;",
    "OSViMode":    "typedef struct OSViMode_s { u32 type; u32 comRegs[4]; u32 fldRegs[2][7]; } OSViMode;",
    "OSViContext": "typedef struct OSViContext_s { u16 state; u16 retraceCount; void *framep; struct OSViMode_s *modep; u32 control; struct OSMesgQueue_s *msgq; OSMesg msg; } OSViContext;",
}

# ---------------------------------------------------------------------------
# N64 OS type sets
# ---------------------------------------------------------------------------
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool",
    "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

N64_OS_OPAQUE_TYPES = {
    "OSPfs", "OSContStatus", "OSContPad", "OSPiHandle",
    "OSMesgQueue", "OSThread", "OSIoMesg", "OSTimer",
    "OSScTask", "OSTask", "OSScClient", "OSScKiller",
    "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr",
    "OSPfsState", "OSPfsFile", "OSPfsDir", "OSDevMgr",
    "SPTask", "GBIarg",
}

N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
    "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
    "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

# Known global variables with their correct types.
# FIX: __osRunningThread added — exceptasm.cpp accesses it.
N64_KNOWN_GLOBALS = {
    "__osPiTable":        "struct OSPiHandle_s *__osPiTable;",
    "__osFlashHandle":    "struct OSPiHandle_s *__osFlashHandle;",
    "__osSfHandle":       "struct OSPiHandle_s *__osSfHandle;",
    "__osCurrentThread":  "struct OSThread_s *__osCurrentThread;",
    "__osRunQueue":       "struct OSThread_s *__osRunQueue;",
    "__osFaultedThread":  "struct OSThread_s *__osFaultedThread;",
    "__osRunningThread":  "struct OSThread_s *__osRunningThread;",
}

# ---------------------------------------------------------------------------
# Globals that MUST have C linkage when compiled as C++.
# exceptasm.cpp is a .cpp TU that defines these as plain C++ variables, so
# the extern declarations in n64_types.h must agree on linkage.
# ---------------------------------------------------------------------------
_CPP_LINKAGE_GLOBALS = {
    "__osPiTable", "__osFlashHandle", "__osSfHandle",
    "__osCurrentThread", "__osRunQueue", "__osFaultedThread",
    "__osRunningThread",
}

# ---------------------------------------------------------------------------
# Canonical primitives block
# ---------------------------------------------------------------------------
_CORE_PRIMITIVES = """\
#include <stdint.h>
#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
typedef uint8_t  u8;
typedef int8_t   s8;
typedef uint16_t u16;
typedef int16_t  s16;
typedef uint32_t u32;
typedef int32_t  s32;
typedef uint64_t u64;
typedef int64_t  s64;
typedef float    f32;
typedef double   f64;
typedef int      n64_bool;

/* N64 SDK Primitive Aliases */
typedef u32   OSIntMask;
typedef u64   OSTime;
typedef u32   OSId;
typedef s32   OSPri;
typedef void* OSMesg;
#endif
"""

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def normalize_path(filepath: str) -> str:
    """Convert absolute CI paths to repo-relative paths."""
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath:
            return filepath.split(marker)[-1]
    return filepath.lstrip("/") if filepath.startswith("/") else filepath

def strip_auto_preamble(content: str) -> str:
    lines = content.split('\n')
    result = []
    in_auto_block = False
    for line in lines:
        s = line.strip()
        if s.startswith("/* AUTO: forward decl"):
            in_auto_block = True
            continue
        if in_auto_block and re.match(r'(?:typedef\s+)?struct\s+\w+(?:_s)?\s+\w+\s*;', s):
            continue
        in_auto_block = False
        result.append(line)
    return '\n'.join(result)

def _rename_posix_static(content: str, func_name: str, filepath: str) -> Tuple[str, bool]:
    prefix   = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define   = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True

def _opaque_stub(tag: str, size: int = 64) -> str:
    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
    return (
        f"#ifndef {tag}_DEFINED\n"
        f"#define {tag}_DEFINED\n"
        f"struct {struct_tag} {{ long long int force_align[{size}]; }};\n"
        f"typedef struct {struct_tag} {tag};\n"
        f"#endif\n"
    )

def _type_already_defined(tag: str, content: str) -> bool:
    if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content): return True
    if re.search(rf"\btypedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content): return True
    if f"{tag}_DEFINED" in content: return True
    return False

def strip_redefinition(content: str, tag: str) -> str:
    """Brace-matched removal of any struct/typedef definition for tag."""
    changed = True
    while changed:
        changed = False
        # Named struct body
        pattern1 = re.compile(rf"\bstruct\s+{re.escape(tag)}\s*\{{")
        match = pattern1.search(content)
        if match:
            start_idx = match.start()
            pre = content[:start_idx].rstrip()
            if pre.endswith("typedef"):
                start_idx = pre.rfind("typedef")
            brace_idx = content.find('{', match.start())
            open_braces, curr_idx = 1, brace_idx + 1
            while curr_idx < len(content) and open_braces > 0:
                if content[curr_idx] == '{': open_braces += 1
                elif content[curr_idx] == '}': open_braces -= 1
                curr_idx += 1
            semi_idx = content.find(';', curr_idx)
            if semi_idx != -1:
                content = content[:start_idx] + f"/* AUTO-STRIPPED RE-DEF: {tag} */\n" + content[semi_idx+1:]
                changed = True
                continue

        # Anonymous typedef body ending in tag
        idx = 0
        while True:
            match = re.search(r"\btypedef\s+struct\b[^{]*\{", content[idx:])
            if not match: break
            start_idx = idx + match.start()
            brace_idx = content.find('{', start_idx)
            open_braces, curr_idx = 1, brace_idx + 1
            while curr_idx < len(content) and open_braces > 0:
                if content[curr_idx] == '{': open_braces += 1
                elif content[curr_idx] == '}': open_braces -= 1
                curr_idx += 1
            semi_idx = content.find(';', curr_idx)
            if semi_idx != -1:
                tail = content[curr_idx:semi_idx]
                if re.search(rf"\b{re.escape(tag)}\b", tail):
                    content = content[:start_idx] + f"/* AUTO-STRIPPED TYPEDEF ALIAS: {tag} */\n" + content[semi_idx+1:]
                    changed = True
                    break
                idx = semi_idx + 1
            else:
                idx = curr_idx + 1
        if changed: continue

        c_new, n = re.subn(rf"\btypedef\s+(?:struct\s+)?[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;", f"/* STRIPPED LOOSE TYPEDEF: {tag} */", content)
        if n > 0: content, changed = c_new, True
        c_new, n = re.subn(rf"\bstruct\s+{re.escape(tag)}\s*;", f"/* STRIPPED FWD DECL: {tag} */", content)
        if n > 0: content, changed = c_new, True
    return content

def repair_unterminated_conditionals(content: str) -> str:
    """
    Scan for #ifndef/#ifdef/#if that are never closed and remove those orphaned guards.
    This prevents 'unterminated conditional directive' errors in n64_types.h.
    """
    lines = content.split('\n')
    stack = []  # list of (line_index, directive_text)
    output = list(lines)
    remove = set()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'#\s*(?:ifndef|ifdef|if)\b', stripped):
            stack.append(i)
        elif re.match(r'#\s*endif\b', stripped):
            if stack:
                stack.pop()
            # else: extra #endif — also bad but less common
    # Any remaining unclosed #ifndef/#ifdef → mark for removal
    for idx in stack:
        remove.add(idx)
        # Also remove the matching #define on the next non-empty line
        for j in range(idx + 1, min(idx + 4, len(lines))):
            if lines[j].strip().startswith('#define') or lines[j].strip().startswith('#endif'):
                remove.add(j)
                break

    if not remove:
        return content
    result = [line for i, line in enumerate(output) if i not in remove]
    return '\n'.join(result)

# ---------------------------------------------------------------------------
# ensure_types_header_base — aggressive primitive cleanup
# ---------------------------------------------------------------------------
def clean_conflicting_typedefs():
    if not os.path.exists(TYPES_HEADER): return
    content = original = read_file(TYPES_HEADER)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
    if content != original: write_file(TYPES_HEADER, content)

def ensure_types_header_base() -> str:
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content: content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    # Strip existing primitives block for clean re-injection
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)

    # Wipe all loose primitive typedefs
    for p in ["u8","s8","u16","s16","u32","s32","u64","s64","f32","f64","n64_bool",
              "OSIntMask","OSTime","OSId","OSPri","OSMesg"]:
        content = re.sub(rf"\btypedef\s+[^;]+\b{re.escape(p)}\s*;", "", content)

    # Scrub structural stubs for primitive aliases
    for p in ["OSIntMask","OSTime","OSId","OSPri","OSMesg"]:
        content = re.sub(rf"(?:typedef\s+)?(?:struct\s+)?{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(p)}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s+{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{re.escape(p)}(?:_s)?\s*;\n?", "", content)

    # Re-inject canonical primitives after #pragma once
    content = content.replace("#pragma once", f"#pragma once\n{_CORE_PRIMITIVES}", 1)

    # Repair any unterminated preprocessor conditionals before writing
    content = repair_unterminated_conditionals(content)

    write_file(TYPES_HEADER, content)
    return content

# ---------------------------------------------------------------------------
# C++ linkage wrapper helpers
# ---------------------------------------------------------------------------
_EXTERN_C_OPEN  = '\n#ifdef __cplusplus\nextern "C" {\n#endif\n'
_EXTERN_C_CLOSE = '\n#ifdef __cplusplus\n}\n#endif\n'

def _wrap_extern_c_in_header(glob_name: str, types_content: str) -> Tuple[str, bool]:
    """
    Find the bare 'extern struct ... *glob_name;' line in types_content
    (possibly inside a #ifndef guard block) and wrap it with extern "C".
    Returns (new_content, changed).
    """
    # Pattern: the extern declaration line for this global, NOT already wrapped
    decl_pat = re.compile(
        rf"(#ifndef {re.escape(glob_name)}_DEFINED\n"
        rf"#define {re.escape(glob_name)}_DEFINED\n)"
        rf"(extern\s+[^\n]+\b{re.escape(glob_name)}\b[^\n]*\n)"
        rf"(#endif\n?)",
        re.MULTILINE,
    )
    m = decl_pat.search(types_content)
    if m:
        guard_open, decl_line, guard_close = m.group(1), m.group(2), m.group(3)
        already_wrapped = _EXTERN_C_OPEN in types_content[max(0, m.start()-80):m.end()+80]
        if already_wrapped:
            return types_content, False
        replacement = (
            guard_open +
            _EXTERN_C_OPEN +
            decl_line +
            _EXTERN_C_CLOSE +
            guard_close
        )
        new_content = types_content[:m.start()] + replacement + types_content[m.end():]
        return new_content, True

    # Fallback: bare extern line without guard
    bare_pat = re.compile(
        rf"^(extern\s+[^\n]+\b{re.escape(glob_name)}\b[^\n]*\n)",
        re.MULTILINE,
    )
    m = bare_pat.search(types_content)
    if m:
        already_wrapped = _EXTERN_C_OPEN in types_content[max(0, m.start()-80):m.end()+80]
        if already_wrapped:
            return types_content, False
        replacement = _EXTERN_C_OPEN + m.group(1) + _EXTERN_C_CLOSE
        new_content = types_content[:m.start()] + replacement + types_content[m.end():]
        return new_content, True

    return types_content, False

# ---------------------------------------------------------------------------
# Log scraper — self-healing
# ---------------------------------------------------------------------------
def _scrape_logs_into_categories(categories: dict) -> None:
    log_candidates = [
        "Android/failed_files.log", "Android/full_build_log.txt",
        "full_build_log.txt", "build_log.txt", "Android/build_log.txt",
    ]
    try:
        for f in os.listdir("."):
            if f.endswith((".txt", ".log")): log_candidates.append(f)
    except Exception: pass

    # Type-coerce all category lists
    for key in ["missing_types","posix_reserved_conflict","struct_redef","typedef_redef"]:
        categories.setdefault(key, [])
        if isinstance(categories[key], set): categories[key] = list(categories[key])

    for key in ["undeclared_identifiers","implicit_func_stubs","need_struct_body","not_a_pointer"]:
        categories.setdefault(key, set())
        if isinstance(categories[key], list): categories[key] = set(categories[key])

    # FIX: new category for C++ language-linkage mismatches
    categories.setdefault("cpp_linkage_extern", set())

    # FIX: new category for structs whose fields can be synthesised from error snippets.
    # Maps type_name -> set of field names observed in member-reference errors.
    categories.setdefault("synthesized_struct_bodies", {})

    mt  = categories["missing_types"]
    pc  = categories["posix_reserved_conflict"]
    sr  = categories["struct_redef"]
    ui  = categories["undeclared_identifiers"]
    ifs = categories["implicit_func_stubs"]
    nsb = categories["need_struct_body"]
    nap = categories["not_a_pointer"]
    cle = categories["cpp_linkage_extern"]

    for log_file in set(log_candidates):
        if not os.path.exists(log_file): continue
        content = read_file(log_file)

        # Unknown type names
        for m in re.finditer(r"(?m)^(/[^\s:]+\.(?:c|cpp)[^:]*):(?:\d+):(?:\d+):\s+error:\s+unknown type name '(\w+)'", content):
            filepath, tag = normalize_path(m.group(1)), m.group(2)
            if not any(isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag for x in mt):
                mt.append((filepath, tag))
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            tag = m.group(1)
            if not any((isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag) or x==tag for x in mt):
                mt.append(tag)

        # POSIX static conflicts
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+static declaration of '(\w+)' follows non-static declaration", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in pc: pc.append(entry)

        # Struct / typedef redefinitions in source files
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+redefinition of '(\w+)'", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in sr: sr.append(entry)
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+typedef redefinition.*?vs '(?:struct )?(\w+)'", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in sr: sr.append(entry)

        # n64_types.h typedef redefinition — wipe and re-inject body
        for m in re.finditer(r"n64_types\.h:\d+:\d+:\s+error:\s+typedef redefinition.*?'(?:struct )?(\w+)'", content):
            nsb.add(m.group(1))

        # Undeclared identifiers
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+use of undeclared identifier '(\w+)'", content):
            ui.add(m.group(2))

        # Implicit functions
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+implicit declaration of function '(\w+)'", content):
            ifs.add(m.group(2))

        # Incomplete type member access
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+member access into incomplete type '(?:struct )?(\w+)'", content):
            nsb.add(m.group(2))

        # Member reference not a pointer
        for m in re.finditer(r"error:\s+member reference (?:base )?type '.*?' is not a (?:pointer|structure or union)\n([^\n]+)\n", content):
            snippet = m.group(1)
            for mm in re.finditer(r'([A-Za-z0-9_]+)(?:->|\.)', snippet):
                nap.add(mm.group(1))

        # Subscript of incomplete type
        for m in re.finditer(r"error:\s+subscript of pointer to incomplete type '(?:struct )?(\w+)'", content):
            nsb.add(m.group(1))

        # FIX: Cross-correlate 'unknown type name' with 'member reference base type void'
        # to synthesise real struct bodies from field names seen in error snippets.
        # Strategy: collect every field name accessed via -> or . on variables whose
        # declared type is the unknown type, keyed by type name.
        ssb = categories["synthesized_struct_bodies"]
        # Collect unknown type names from this log
        _unk_types_in_log: set = set()
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            _unk_types_in_log.add(m.group(1))
        # For each 'member reference base type void' snippet, extract field names
        # and attribute them to the unknown type(s) that appear in surrounding context
        for m in re.finditer(
            r"error:\s+member reference (?:base )?type '(?:void|long long\[?\d*\]?)' is not a (?:pointer|structure or union)\n([^\n]+)\n",
            content,
        ):
            snippet = m.group(1)
            # Extract all field names (after -> or .)
            for fm in re.finditer(r'(?:->|\.)(\w+)', snippet):
                field = fm.group(1)
                # Try to find the type of the variable being dereferenced
                # from the variable name in the snippet (before -> or .)
                for vm in re.finditer(r'([A-Za-z_]\w*)(?:->|\.)', snippet):
                    var = vm.group(1)
                    # If this variable is declared as one of the unknown types,
                    # attribute the field to that type
                    for unk in _unk_types_in_log:
                        # Check that the log mentions "unk *var" or "unk var" near this error
                        if re.search(
                            rf"\b{re.escape(unk)}\s*\*?\s*{re.escape(var)}\b",
                            content,
                        ):
                            if unk not in ssb:
                                ssb[unk] = set()
                            ssb[unk].add(field)
        # Also extract fields from "expected expression" lines that follow cast failures
        # Pattern: LetterFloorTile *ptr = (LetterFloorTile *)arg3;
        # The type name appears in both the unknown-type error and the cast line.
        for unk in _unk_types_in_log:
            # Look for all -> / . accesses on any pointer of this type
            for m in re.finditer(
                rf"\b{re.escape(unk)}\s*\*\s*\w+\s*[;=]",
                content,
            ):
                pass  # variable declarations — we care about accesses
            for m in re.finditer(
                rf"(?:->|\.)(\w+)(?:\s*[=<>!+\-*/]|\s*!=|\s*==)",
                content,
            ):
                field = m.group(1)
                # Confirm this access appears in a block that also mentions unk
                start = max(0, m.start() - 300)
                end   = min(len(content), m.end() + 300)
                ctx = content[start:end]
                if re.search(rf"\b{re.escape(unk)}\b", ctx):
                    if unk not in ssb:
                        ssb[unk] = set()
                    ssb[unk].add(field)

        # Redeclaration with different type (e.g. __osPiTable)
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+redeclaration of '(\w+)' with a different type", content):
            filepath, var = normalize_path(m.group(1)), m.group(2)
            categories.setdefault("type_mismatch_globals", [])
            if (filepath, var) not in categories["type_mismatch_globals"]:
                categories["type_mismatch_globals"].append((filepath, var))

        # FIX: C++ language linkage mismatch
        # Pattern: error: declaration of 'SYMBOL' has a different language linkage
        # Covers both .c and .cpp files — only .cpp files actually cause this.
        for m in re.finditer(
            r"(?m)^(/[^\s:]+\.(?:c|cpp)[^:]*):(?:\d+):(?:\d+):\s+error:\s+declaration of '(\w+)' has a different language linkage",
            content,
        ):
            cle.add(m.group(2))

        # Also catch the condensed summary line variant (no file prefix)
        for m in re.finditer(r"declaration of '(\w+)' has a different language linkage", content):
            cle.add(m.group(1))

        # FIX: member reference base type 'long long[N]' is not a structure — schedules
        # the owning struct for full-body re-injection (not just opaque stub).
        # This catches __osRunningThread->context.status where context was long long[67].
        for m in re.finditer(
            r"error:\s+member reference base type '.*?' is not a structure or union\n([^\n]+)\n",
            content,
        ):
            snippet = m.group(1)
            # Extract the object before -> or .
            for mm in re.finditer(r'([A-Za-z_]\w*)(?:->|\.)', snippet):
                var = mm.group(1)
                # If this is a known global pointing at a known struct, schedule struct re-injection
                if var in N64_KNOWN_GLOBALS:
                    decl = N64_KNOWN_GLOBALS[var]
                    type_match = re.search(r'struct\s+(\w+)\s*\*', decl)
                    if type_match:
                        struct_name = type_match.group(1).rstrip('_s')
                        # strip trailing _s to get the typedef name
                        typedef_name = struct_name if not struct_name.endswith('_s') else struct_name[:-2]
                        nsb.add(typedef_name)

# ---------------------------------------------------------------------------
# Main fix dispatcher
# ---------------------------------------------------------------------------
def apply_fixes(categories: dict, intelligence_level: int = 1) -> Tuple[int, set]:
    fixes       = 0
    fixed_files = set()

    if intelligence_level >= 3:
        ACTIVE_MACROS   = PHASE_3_MACROS
        ACTIVE_STRUCTS  = {k:v for k,v in {**_N64_OS_STRUCT_BODIES, **PHASE_3_STRUCTS}.items() if k not in SDK_DEFINES_THESE}
    elif intelligence_level == 2:
        ACTIVE_MACROS   = PHASE_2_MACROS
        ACTIVE_STRUCTS  = {k:v for k,v in _N64_OS_STRUCT_BODIES.items() if k not in SDK_DEFINES_THESE}
    else:
        ACTIVE_MACROS   = PHASE_1_MACROS
        ACTIVE_STRUCTS  = {}

    for k, v in _EP_STRUCTS.items():
        if k not in SDK_DEFINES_THESE:
            ACTIVE_STRUCTS[k] = v

    # At intelligence level 2+, schedule full bodies for all known structs
    if intelligence_level >= 2:
        for tag in ACTIVE_STRUCTS.keys():
            categories.setdefault("need_struct_body", set()).add(tag)

    _scrape_logs_into_categories(categories)
    clean_conflicting_typedefs()
    types_content = ensure_types_header_base()

    # ------------------------------------------------------------------
    # Level 2+: Cleanup phase — scrub incorrect guesses, wrong externs
    # ------------------------------------------------------------------
    if intelligence_level >= 2:
        original_types = types_content
        scrub_targets = (set(ACTIVE_STRUCTS.keys()) | N64_OS_OPAQUE_TYPES
                         | set(ACTIVE_MACROS.keys())
                         | {"__osPiTable","__OSBlockInfo","__OSTranxInfo",
                            "__osCurrentThread","__osRunQueue","__osFaultedThread",
                            "__osRunningThread"})
        for target in scrub_targets:
            # Remove wrong extern long long or void* declarations
            types_content = re.sub(
                rf"(?m)^#ifndef {re.escape(target)}_DEFINED\n#define {re.escape(target)}_DEFINED\nextern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?\s*;\n#endif\n?",
                "", types_content)
            types_content = re.sub(
                rf"(?m)^extern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?\s*;\n?",
                "", types_content)
        if types_content != original_types:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

        # Inject correctly-typed globals (e.g. __osPiTable as OSPiHandle*)
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for glob, decl in N64_KNOWN_GLOBALS.items():
            if glob not in types_content:
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # FIX: C++ language linkage — wrap offending externs in extern "C"
    # ------------------------------------------------------------------
    if categories.get("cpp_linkage_extern"):
        types_content = read_file(TYPES_HEADER)
        linkage_fixed = False
        for glob in sorted(categories["cpp_linkage_extern"]):
            if not isinstance(glob, str): continue
            # Only wrap globals we know need it (those declared in .cpp TUs as C++ vars)
            if glob not in _CPP_LINKAGE_GLOBALS and glob not in N64_KNOWN_GLOBALS:
                continue
            new_types, changed = _wrap_extern_c_in_header(glob, types_content)
            if changed:
                types_content = new_types
                linkage_fixed = True
                logger.info(f"  [linkage] Wrapped extern \"{glob}\" in extern \"C\"")
        if linkage_fixed:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Fix type_mismatch_globals — remove wrong extern for re-injection
    # ------------------------------------------------------------------
    if categories.get("type_mismatch_globals"):
        types_content = read_file(TYPES_HEADER)
        changed = False
        for item in categories["type_mismatch_globals"]:
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            _, var = item[0], item[1]
            # Remove the wrong extern declaration entirely so correct one can take over
            types_content = re.sub(
                rf"(?m)^#ifndef {re.escape(var)}_DEFINED\n.*?#define {re.escape(var)}_DEFINED\nextern[^\n]+{re.escape(var)}[^\n]*\n#endif\n?",
                "", types_content, flags=re.DOTALL)
            types_content = re.sub(
                rf"(?m)^extern[^\n]+\b{re.escape(var)}\b[^\n]*\n?", "", types_content)
            changed = True
            # Schedule correct re-injection via known globals
            if var in N64_KNOWN_GLOBALS:
                if f"{var}_DEFINED" not in types_content:
                    decl = N64_KNOWN_GLOBALS[var]
                    types_content += f"\n#ifndef {var}_DEFINED\n#define {var}_DEFINED\nextern {decl}\n#endif\n"
        if changed:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Macro scrubber — remove 0-value stubs for now-known types
    # ------------------------------------------------------------------
    known_type_tags: Set[str] = set()
    for item in categories.get("missing_types", []):
        if isinstance(item,(list,tuple)) and len(item)>=2: known_type_tags.add(item[1])
        elif isinstance(item, str): known_type_tags.add(item)
    for tag in categories.get("need_struct_body", set()): known_type_tags.add(tag) if isinstance(tag,str) else None
    for item in categories.get("incomplete_sizeof", []):
        if isinstance(item,(list,tuple)) and len(item)>=2: known_type_tags.add(item[1])
    for tag in categories.get("conflict_typedef", []): known_type_tags.add(tag) if isinstance(tag,str) else None
    known_type_tags.update(N64_OS_OPAQUE_TYPES)
    known_type_tags.update(ACTIVE_STRUCTS.keys())

    macros_cleaned = False
    for tag in known_type_tags:
        p1 = rf"(?m)^\s*#ifndef {re.escape(tag)}\s*\n\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(p1, "", types_content)
        p2 = rf"(?m)^\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
        types_content, n2 = re.subn(p2, "", types_content)
        if n1 + n2 > 0:
            macros_cleaned = True
            fixes += 1
    if macros_cleaned: write_file(TYPES_HEADER, types_content)

    # ------------------------------------------------------------------
    # Not-a-pointer repair
    # ------------------------------------------------------------------
    if categories.get("not_a_pointer"):
        types_content = read_file(TYPES_HEADER)
        changed = False
        for member in sorted(categories["not_a_pointer"]):
            if not isinstance(member, str): continue
            new_types, n = re.subn(
                rf"\blong\s+long\s+int\s+{re.escape(member)}\s*;",
                f"void* {member}; /* AUTO-FIX: cast to pointer */", types_content)
            if n > 0:
                types_content = new_types
                changed = True
        if changed:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Implicit function stubs
    # ------------------------------------------------------------------
    if categories.get("implicit_func_stubs"):
        types_content = read_file(TYPES_HEADER)
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
        stubs_content = read_file(STUBS_FILE)
        std_funcs = {"sinf","cosf","sqrtf","abs","fabs","pow","floor","ceil","round",
                     "memcpy","memset","strlen","strcpy","strncpy","strcmp","memcmp",
                     "malloc","free","exit","atoi","rand","srand"}
        funcs_added = False
        for func in sorted(categories["implicit_func_stubs"]):
            if not isinstance(func,str) or func in std_funcs: continue
            proto = f"long long int {func}();"
            if proto not in types_content:
                types_content += f"\n#ifndef {func}_DEFINED\n#define {func}_DEFINED\nextern {proto}\n#endif\n"
                funcs_added = True
            impl = f"long long int {func}() {{ return 0; }}\n"
            if impl not in stubs_content:
                stubs_content += impl
                funcs_added = True
        if funcs_added:
            write_file(TYPES_HEADER, types_content)
            write_file(STUBS_FILE, stubs_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Undeclared identifiers
    # ------------------------------------------------------------------
    if categories.get("undeclared_identifiers"):
        types_content = read_file(TYPES_HEADER)
        idents_added = False
        for ident in sorted(categories["undeclared_identifiers"]):
            if not isinstance(ident, str): continue
            # Skip if already covered by known globals
            if ident in N64_KNOWN_GLOBALS: continue
            # Skip if already in active macros
            if ident in ACTIVE_MACROS:
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} {ACTIVE_MACROS[ident]}\n#endif\n"
                    idents_added = True
                continue
            if ident.isupper() or ident.startswith(("G_","OS_","PI_","PFS_","LEO_","ADPCM","UNITY","MAX_")):
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* AUTO-INJECTED UNDECLARED IDENTIFIER */\n#endif\n"
                    idents_added = True
            else:
                decl = f"extern long long int {ident};"
                if decl not in types_content and f"{ident}_DEFINED" not in types_content:
                    types_content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\n{decl}\n#endif\n"
                    idents_added = True
        if idents_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Conflict typedef cleanup
    # ------------------------------------------------------------------
    for type_name in sorted(categories.get("conflict_typedef", [])):
        if type_name in SDK_DEFINES_THESE: continue
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(?:typedef\s+)?(?:struct\s+)?{re.escape(type_name)}\s*\{{[^}}]*\}}\s*{re.escape(type_name)}?\s*;\n?"
        new_types, n = re.subn(pattern, "", types_content)
        new_types = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int)\s+{re.escape(type_name)}\s*;", "", new_types)
        if n > 0:
            if f"struct {type_name}_s {{" not in new_types:
                new_types += f"\nstruct {type_name}_s {{ long long int force_align[64]; }};\n"
            write_file(TYPES_HEADER, new_types)
            types_content = new_types
            fixes += 1

    # ------------------------------------------------------------------
    # Missing members injection
    # ------------------------------------------------------------------
    array_names = {"id","label","name","buffer","data","str","string","temp"}
    for item in sorted(categories.get("missing_members", [])):
        if not isinstance(item,(list,tuple)) or len(item)<2: continue
        struct_name, member_name = item[0], item[1]
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(struct\s+{re.escape(struct_name)}\s*\{{)([^}}]*?)(\}})"
        def inject_member(match, mn=member_name, an=array_names):
            body = match.group(2)
            if mn not in body:
                if mn in an: field = f"    unsigned char {mn}[128]; /* AUTO-ARRAY */\n"
                elif any(x in mn.lower() for x in ["ptr","func","cb"]): field = f"    void* {mn}; /* AUTO-POINTER */\n"
                else: field = f"    long long int {mn};\n"
                return f"{match.group(1)}{body}{field}{match.group(3)}"
            return match.group(0)
        if re.search(pattern, types_content):
            new_types, n = re.subn(pattern, inject_member, types_content)
            if n > 0:
                write_file(TYPES_HEADER, new_types)
                fixes += 1
        else:
            mn = member_name
            field = (f"unsigned char {mn}[128];" if mn in array_names else
                     f"void* {mn};" if any(x in mn.lower() for x in ["ptr","func","cb"]) else
                     f"long long int {mn};")
            types_content += f"\nstruct {struct_name} {{\n    {field}\n    long long int force_align[64];\n}};\n"
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Variable redefinitions
    # ------------------------------------------------------------------
    for item in sorted(categories.get("redefinition", [])):
        if not isinstance(item,(list,tuple)) or len(item)<2: continue
        filepath, var = item[0], item[1]
        if os.path.exists(filepath):
            content = read_file(filepath)
            new_content, n = re.subn(rf"^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */", content, flags=re.MULTILINE)
            if n > 0:
                write_file(filepath, new_content)
                fixed_files.add(filepath)
                fixes += 1

    # ------------------------------------------------------------------
    # Missing types → opaque stubs or full bodies
    # ------------------------------------------------------------------
    for item in sorted(categories.get("missing_types", []), key=str):
        if isinstance(item,(list,tuple)) and len(item)>=2: filepath, tag = item[0], item[1]
        elif isinstance(item, str): filepath, tag = None, item
        else: continue
        if not isinstance(tag, str): continue

        # Skip SDK-owned types entirely — never inject these
        if tag in SDK_DEFINES_THESE:
            continue

        types_content = read_file(TYPES_HEADER)
        if tag in N64_PRIMITIVES:
            pass  # already in primitives block
        elif tag in N64_AUDIO_STATE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                write_file(TYPES_HEADER, types_content); fixes += 1
        elif tag in ACTIVE_STRUCTS:
            categories.setdefault("need_struct_body", set()).add(tag)
        elif tag in N64_OS_OPAQUE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += "\n" + _opaque_stub(tag, size=64)
                write_file(TYPES_HEADER, types_content); fixes += 1
        else:
            if not re.search(rf"\b{re.escape(tag)}\b", types_content):
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content)
                fixed_files.add(TYPES_HEADER); fixes += 1

        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # FIX: Synthesized struct bodies — build real structs from observed fields.
    # This handles cases like LetterFloorTile where the type is unknown AND its
    # members are accessed in the same TU.  An opaque stub is insufficient because
    # the code does ptr->meshId, ptr->state, ptr->timeDeltaSum, etc.
    # We infer reasonable field types from naming conventions and inject a complete
    # struct definition into n64_types.h, replacing any prior opaque stub.
    # ------------------------------------------------------------------
    if categories.get("synthesized_struct_bodies"):
        types_content = read_file(TYPES_HEADER)
        synth_added = False

        def _infer_field_type(field: str) -> str:
            fl = field.lower()
            if any(x in fl for x in ["time", "delta", "sum", "ratio", "scale", "speed",
                                       "angle", "dist", "frac", "f_", "float"]):
                return "f32"
            if any(x in fl for x in ["ptr", "next", "prev", "parent", "child",
                                       "func", "cb", "handler", "addr"]):
                return "void*"
            if any(x in fl for x in ["mesh", "meshid", "state", "status", "mode",
                                       "type", "index", "count", "id", "num", "flag"]):
                return "s32"
            return "s32"

        for type_name, fields in sorted(categories["synthesized_struct_bodies"].items()):
            if not fields:
                continue
            if type_name in SDK_DEFINES_THESE:
                continue
            existing = _type_already_defined(type_name, types_content)
            is_opaque = existing and re.search(
                rf"struct\s+{re.escape(type_name)}(?:_s)?\s*\{{\s*long\s+long\s+int\s+force_align",
                types_content,
            )
            if existing and not is_opaque:
                continue  # already has a real body

            if is_opaque:
                types_content = strip_redefinition(types_content, type_name)
                types_content = strip_redefinition(types_content, f"{type_name}_s")
                types_content = re.sub(
                    rf"#ifndef {re.escape(type_name)}_DEFINED[\s\S]*?#endif\n?",
                    "", types_content,
                )

            field_lines = [f"    {_infer_field_type(f)} {f};" for f in sorted(fields)]
            struct_tag  = f"{type_name}_s"
            fields_str  = "\n".join(field_lines)
            struct_body = (
                f"/* AUTO-SYNTHESIZED from member-access errors */\n"
                f"#ifndef {type_name}_DEFINED\n"
                f"#define {type_name}_DEFINED\n"
                f"typedef struct {struct_tag} {{\n"
                f"{fields_str}\n"
                f"}} {type_name};\n"
                f"#endif\n"
            )
            types_content += "\n" + struct_body
            synth_added = True
            logger.info(f"  [synth-struct] Synthesised {type_name} with fields: {sorted(fields)}")

        if synth_added:
            types_content = repair_unterminated_conditionals(types_content)
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Audio state types
    # ------------------------------------------------------------------
    if categories.get("unknown_audio_state_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        for t in sorted(categories["unknown_audio_state_types"]):
            if not isinstance(t,str) or t not in N64_AUDIO_STATE_TYPES: continue
            if not _type_already_defined(t, types_content):
                types_content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
                added = True
        if added: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Extraneous brace cleanup
    # ------------------------------------------------------------------
    if categories.get("extraneous_brace"):
        types_content = read_file(TYPES_HEADER)
        original = types_content
        types_content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", types_content)
        types_content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Conflicting implicit-type prototypes
    # ------------------------------------------------------------------
    for item in sorted(categories.get("conflicting_types",[]), key=str):
        if not isinstance(item,(list,tuple)) or len(item)<2: continue
        filepath, func = item[0], item[1]
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        pattern = rf"(?:^|\n)([A-Za-z_][A-Za-z0-9_\s\*]+?)\s+\b{re.escape(func)}\s*\([^;{{]*\)\s*\{{"
        match = re.search(pattern, content)
        if match:
            sig_full = match.group(0)
            prototype = sig_full[:sig_full.rfind('{')].strip() + ";"
            if prototype not in content:
                includes = list(re.finditer(r"#include\s+.*?\n", content))
                injection = f"\n/* AUTO: resolve conflicting implicit type */\n{prototype}\n"
                idx = includes[-1].end() if includes else 0
                content = content[:idx] + injection + content[idx:]
                write_file(filepath, content)
                fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Missing n64_types.h include
    # ------------------------------------------------------------------
    for item in sorted(categories.get("missing_n64_types",[]), key=str):
        filepath = item if isinstance(item,str) else str(item)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'n64_types.h"' not in content and '<n64_types.h>' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Actor pointer injection
    # ------------------------------------------------------------------
    for item in sorted(categories.get("actor_pointer",[]), key=str):
        filepath = item if isinstance(item,str) else str(item)
        if not os.path.exists(filepath): continue
        content = original = read_file(filepath)
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Local struct forward declarations
    # ------------------------------------------------------------------
    if categories.get("local_struct_fwd"):
        file_to_types: dict = defaultdict(set)
        for item in categories["local_struct_fwd"]:
            if isinstance(item,(list,tuple)) and len(item)>=2: file_to_types[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t)>1 and t[0] in ('s','S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content: fwd_lines.append(fwd_decl)
            if fwd_lines:
                write_file(filepath, "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n" + content)
                fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Typedef / struct redefinitions in source files
    # ------------------------------------------------------------------
    fixd_files: set = set()
    for item in categories.get("typedef_redef",[]):
        if isinstance(item,(list,tuple)) and len(item)>=1: fixd_files.add(item[0])
    for item in categories.get("struct_redef",[]):
        if isinstance(item,(list,tuple)) and len(item)>=1: fixd_files.add(item[0])

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content  = read_file(filepath)
        original = content
        content  = strip_auto_preamble(content)

        for item in categories.get("struct_redef",[]):
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            fp2, tag = item[0], item[1]
            if fp2 != filepath: continue
            if tag in SDK_DEFINES_THESE: continue
            content = strip_redefinition(content, tag)

        for item in categories.get("typedef_redef",[]):
            if not isinstance(item,(list,tuple)) or len(item)<3: continue
            fp2, type1, type2 = item[0], item[1], item[2]
            if fp2 != filepath: continue
            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2): continue
            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            anon_pat = rf"typedef\s+struct\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_pat, content):
                def _anon_sub(m, tt=target_tag): return f"typedef struct {tt} {{{m.group(1)}}} {m.group(2)};"
                content, _ = re.subn(anon_pat, _anon_sub, content)
            else:
                bad_pat = rf"(?:typedef\s+)?struct\s+{re.escape(alias)}\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
                if re.search(bad_pat, content):
                    def _bad_sub(m, tt=target_tag): return f"typedef struct {tt} {{{m.group(1)}}} {m.group(2)};"
                    content, _ = re.subn(bad_pat, _bad_sub, content)
                else:
                    content, _ = re.subn(r"\bstruct\s+" + re.escape(alias) + r"\b", f"struct {target_tag}", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Incomplete sizeof
    # ------------------------------------------------------------------
    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen: set = set()
        for item in categories["incomplete_sizeof"]:
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            filepath, tag = item[0], item[1]
            if tag in seen or tag in SDK_DEFINES_THESE: continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in ACTIVE_STRUCTS: continue
            is_sdk = (tag.isupper() or tag.startswith(("OS","SP","DP","AL","GU","G_"))
                      or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Static / POSIX conflicts
    # ------------------------------------------------------------------
    seen_static: set = set()
    for cat in ["static_conflict","posix_conflict","posix_reserved_conflict"]:
        for item in categories.get(cat, []):
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            filepath, func_name = item[0], item[1]
            key = (filepath, func_name)
            if key in seen_static: continue
            seen_static.add(key)
            if not func_name or not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath); fixes += 1
                continue
            prefix    = os.path.basename(filepath).split('.')[0]
            macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
            if macro_fix not in content:
                anchor  = '#include "ultra/n64_types.h"'
                content = (content.replace(anchor, anchor + macro_fix) if anchor in content else macro_fix + content)
                write_file(filepath, content)
                fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Undeclared macros
    # ------------------------------------------------------------------
    if categories.get("undeclared_macros"):
        types_content = read_file(TYPES_HEADER)
        macros_added  = False
        for macro in sorted(categories["undeclared_macros"]):
            if not isinstance(macro, str): continue
            if macro in KNOWN_FUNCTION_MACROS:
                defn = KNOWN_FUNCTION_MACROS[macro]
                if defn not in types_content:
                    types_content += f"\n{defn}\n"; macros_added = True
            elif macro in ACTIVE_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {ACTIVE_MACROS[macro]}\n#endif\n"
                    macros_added = True
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Implicit function declarations → system headers
    # ------------------------------------------------------------------
    if categories.get("implicit_func"):
        math_funcs   = {"sinf","cosf","sqrtf","abs","fabs","pow","floor","ceil","round"}
        string_funcs = {"memcpy","memset","strlen","strcpy","strncpy","strcmp","memcmp"}
        stdlib_funcs = {"malloc","free","exit","atoi","rand","srand"}
        types_content  = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if not isinstance(func, str): continue
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs:   header = "<stdlib.h>"
            else:                        continue
            if f"#include {header}" not in types_content:
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Undefined linker symbols → stubs
    # ------------------------------------------------------------------
    if categories.get("undefined_symbols"):
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace("add_library(", "add_library(\n        ultra/n64_stubs.c")
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added    = False
        for sym in sorted(categories["undefined_symbols"]):
            if not isinstance(sym, str): continue
            if sym.startswith("_Z") or "vtable" in sym: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added: write_file(STUBS_FILE, existing_stubs); fixes += 1

    # ------------------------------------------------------------------
    # Audio-state opaque types
    # ------------------------------------------------------------------
    if categories.get("audio_states"):
        types_content = read_file(TYPES_HEADER)
        audio_added   = False
        for t in sorted(categories["audio_states"]):
            if not isinstance(t, str): continue
            if not _type_already_defined(t, types_content):
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Undeclared N64 platform types
    # ------------------------------------------------------------------
    if categories.get("undeclared_n64_types"):
        types_content = read_file(TYPES_HEADER)
        k_added = False
        for item in sorted(categories["undeclared_n64_types"], key=str):
            if isinstance(item,(list,tuple)) and len(item)>=2: filepath, t = item[0], item[1]
            elif isinstance(item, str): filepath, t = None, item
            else: continue
            if not isinstance(t,str) or t in N64_PRIMITIVES or t in SDK_DEFINES_THESE: continue
            if t in ACTIVE_STRUCTS: categories.setdefault("need_struct_body", set()).add(t)
            elif t in N64_OS_OPAQUE_TYPES:
                if not _type_already_defined(t, types_content):
                    types_content += "\n" + _opaque_stub(t); k_added = True
            elif not re.search(rf"\b{re.escape(t)}\b", types_content):
                struct_tag = f"{t}_s" if not t.endswith("_s") else t
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {t};\n"
                types_content += f"\n#ifndef {t}_DEFINED\n#define {t}_DEFINED\n{decl}#endif\n"
                k_added = True
            if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                c = read_file(filepath)
                if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                    fixed_files.add(filepath); fixes += 1
        if k_added: write_file(TYPES_HEADER, types_content); fixes += 1

        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs); fixes += 1

    # ------------------------------------------------------------------
    # Undeclared GBI constants
    # ------------------------------------------------------------------
    if categories.get("undeclared_gbi"):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if not isinstance(ident, str): continue
            if ident in ACTIVE_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {ACTIVE_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in ACTIVE_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                gbi_added = True
        if gbi_added: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # Full struct body rewriter — topologically ordered, SDK-safe
    # ------------------------------------------------------------------
    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added  = False

        ordered_tags = [t for t in ACTIVE_STRUCTS.keys()
                        if t in categories.get("need_struct_body", set())
                        and t not in SDK_DEFINES_THESE]
        other_tags   = sorted([t for t in categories.get("need_struct_body", set())
                                if t not in ACTIVE_STRUCTS and t not in SDK_DEFINES_THESE])

        for tag in ordered_tags + other_tags:
            if not isinstance(tag, str): continue
            body = ACTIVE_STRUCTS.get(tag)
            if not body:
                if tag in N64_OS_OPAQUE_TYPES and not _type_already_defined(tag, types_content):
                    types_content += "\n" + _opaque_stub(tag)
                    bodies_added = True
                continue

            # Space-normalized idempotency check
            norm_body  = re.sub(r'\s+', ' ', body).strip()
            norm_types = re.sub(r'\s+', ' ', types_content)
            if norm_body in norm_types:
                continue

            # Aggressively strip any old definition before replacing
            types_content = strip_redefinition(types_content, tag)
            if not tag.endswith("_s"):
                types_content = strip_redefinition(types_content, f"{tag}_s")
            if tag == "OSPiHandle":
                types_content = strip_redefinition(types_content, "__OSBlockInfo")
                types_content = strip_redefinition(types_content, "__OSTranxInfo")
            # FIX: when re-injecting OSThread, also strip the old __OSThreadContext if present
            if tag == "OSThread":
                types_content = strip_redefinition(types_content, "__OSThreadContext")
                types_content = re.sub(r"#ifndef __OSThreadContext_DEFINED[\s\S]*?#endif\n?", "", types_content)
            types_content = re.sub(rf"#ifndef {re.escape(tag)}_DEFINED[\s\S]*?#endif\n?", "", types_content)
            if tag == "LookAt":
                types_content = re.sub(r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__Light_t\s*;\n?", "", types_content)
                types_content = re.sub(r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__LookAtDir\s*;\n?", "", types_content)
            if tag == "Mtx":
                types_content = re.sub(r"(?m)^typedef\s+union\s*\{[^}]*\}\s*__Mtx_data\s*;\n?", "", types_content)

            types_content += "\n" + body + "\n"
            bodies_added = True

        if bodies_added:
            # Final pass: repair any unterminated conditionals introduced by injection
            types_content = repair_unterminated_conditionals(types_content)
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Local forward-only declarations
    # ------------------------------------------------------------------
    if categories.get("local_fwd_only"):
        file_to_types2: dict = defaultdict(set)
        for item in categories["local_fwd_only"]:
            if isinstance(item,(list,tuple)) and len(item)>=2: file_to_types2[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types2.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{[^}}]*\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
                fwd_decl = f"typedef struct {t}_s {t};"
                fwd = f"/* AUTO: forward decl for type defined below */\n{fwd_decl}\n" if re.search(body_pattern, content) else f"/* AUTO: forward declarations */\n{fwd_decl}\n"
                if fwd_decl not in content:
                    content = fwd + content
                    changed = True
            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # Missing global extern declarations
    # ------------------------------------------------------------------
    if categories.get("missing_globals"):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for item in sorted(categories.get("missing_globals", []), key=str):
            if isinstance(item,(list,tuple)) and len(item)>=2: _, glob = item[0], item[1]
            elif isinstance(item, str): glob = item
            else: continue
            if glob == "actor": continue
            # Use known-good type if available
            if glob in N64_KNOWN_GLOBALS:
                if f"{glob}_DEFINED" not in types_content:
                    types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {N64_KNOWN_GLOBALS[glob]}\n#endif\n"
                    globals_added = True
            elif f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content:
                decl = (f"extern void* {glob};" if glob.endswith(("_ptr","_p")) else f"extern long long int {glob};")
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added: write_file(TYPES_HEADER, types_content); fixes += 1

    return fixes, fixed_files
