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
# Constants & Fallbacks
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
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
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
    "OS_IM_NONE": "0x0000", "OS_IM_1": "0x0001", "OS_IM_2": "0x0002",
    "OS_IM_3": "0x0004", "OS_IM_4": "0x0008", "OS_IM_5": "0x0010",
    "OS_IM_6": "0x0020", "OS_IM_7": "0x0040", "OS_IM_ALL": "0x007F",
    "PFS_ERR_ID_FATAL": "0x10", "PFS_ERR_DEVICE":   "0x02",
    "PFS_ERR_CONTRFAIL":"0x01", "PFS_ERR_INVALID":  "0x03",
    "PFS_ERR_EXIST":    "0x04", "PFS_ERR_NOEXIST":  "0x05",
    "PFS_DATA_ENXIO":   "0x06", "ADPCMFSIZE": "9", "ADPCMVSIZE": "16",
    "UNITY_PITCH": "0x8000", "MAX_RATIO":   "0xFFFF",
    "PI_DOMAIN1":  "0", "PI_DOMAIN2":  "1",
}

PHASE_2_MACROS = {
    **PHASE_1_MACROS,
    "DEVICE_TYPE_64DD": "0x06",
    "LEO_CMD_TYPE_0": "0", "LEO_CMD_TYPE_1": "1", "LEO_CMD_TYPE_2": "2",
    "LEO_SECTOR_MODE": "1", "LEO_TRACK_MODE": "2",
    "LEO_BM_CTL": "0x05000510", "LEO_BM_CTL_RESET": "0",
    "LEO_ERROR_29": "29", "OS_READ": "0", "OS_WRITE": "1",
    "OS_MESG_NOBLOCK": "0", "OS_MESG_BLOCK": "1",
    "PI_STATUS_REG":        "0x04600010", "PI_DRAM_ADDR_REG":     "0x04600000",
    "PI_CART_ADDR_REG":     "0x04600004", "PI_RD_LEN_REG":        "0x04600008",
    "PI_WR_LEN_REG":        "0x0460000C", "PI_STATUS_DMA_BUSY":   "0x01",
    "PI_STATUS_IO_BUSY":    "0x02", "PI_STATUS_ERROR":      "0x04",
    "PI_STATUS_INTERRUPT":  "0x08", "PI_BSD_DOM1_LAT_REG":  "0x04600014",
    "PI_BSD_DOM1_PWD_REG":  "0x04600018", "PI_BSD_DOM1_PGS_REG":  "0x0460001C",
    "PI_BSD_DOM1_RLS_REG":  "0x04600020", "PI_BSD_DOM2_LAT_REG":  "0x04600024",
    "PI_BSD_DOM2_PWD_REG":  "0x04600028", "PI_BSD_DOM2_PGS_REG":  "0x0460002C",
    "PI_BSD_DOM2_RLS_REG":  "0x04600030",
}

PHASE_3_MACROS = {
    **PHASE_2_MACROS,
    "G_ON": "1", "G_OFF": "0",
    "G_RM_AA_ZB_OPA_SURF":  "0x00000000", "G_RM_AA_ZB_OPA_SURF2": "0x00000000",
    "G_RM_AA_ZB_XLU_SURF":  "0x00000000", "G_RM_AA_ZB_XLU_SURF2": "0x00000000",
    "G_ZBUFFER": "0x00000001", "G_SHADE": "0x00000004",
    "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
}

# ---------------------------------------------------------------------------
# N64 struct bodies
# CRITICAL FIX: `errno` is replaced with `errnum` natively to stop NDK collisions
#
# FIX: OSPfs — added all missing members: queue, channel, activebank, banks,
#      dir_size, dir_table, inode_start_page.
#
# FIX: OSThread — context changed from bare array to __OSThreadContext union
#      so member access (context.pc etc.) works from createthread.c.
#
# FIX: OSViMode — comRegs and fldRegs now have named sub-structs so
#      vi*.c member accesses like .ctrl, .width, .burst etc. compile.
#
# FIX: Vtx — added Vtx_n member to union so .n.ob, .n.flag, .n.tc, .n.cn work.
#
# FIX: OSHWIntr — must be u32 integer type, NOT a struct, so bitmask ops work.
#      __OSGlobalIntMask declared as extern OSHWIntr.
#
# FIX: ADPCM_STATE — must be short[ADPCMFSIZE] array typedef so it is
#      implicitly convertible to void* via pointer decay, not a struct.
#
# FIX: OSYieldResult, Vp — added.
# ---------------------------------------------------------------------------
_N64_OS_STRUCT_BODIES = {
    "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;",

    "OSContStatus": "typedef struct OSContStatus_s { u16 type; u8 status; u8 errnum; } OSContStatus;",
    "OSContPad":    "typedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; u8 errnum; } OSContPad;",

    "OSMesgQueue":  "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; s32 validCount; s32 first; s32 msgCount; OSMesg *msg; } OSMesgQueue;",

    # FIX: context is a union with named register fields so createthread.c can
    # do thread->context.pc = ... thread->context.sp = ... etc.
    "OSThread": """\
#ifndef __OSThreadContext_DEFINED
#define __OSThreadContext_DEFINED
typedef union __OSThreadContext_u {
    long long int raw[67];
    struct {
        u64 at, v0, v1, a0, a1, a2, a3;
        u64 t0, t1, t2, t3, t4, t5, t6, t7;
        u64 s0, s1, s2, s3, s4, s5, s6, s7;
        u64 t8, t9;
        u64 gp, sp, s8, ra;
        u64 lo, hi;
        u32 sr, fpcsr;
        u64 pc;
        double fp[32];
    } regs;
} __OSThreadContext;
#endif
typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    struct OSThread_s **queue;
    struct OSThread_s *tlnext;
    u16 state;
    u16 flags;
    OSId id;
    int fp;
    __OSThreadContext context;
} OSThread;""",

    "OSMesgHdr":    "typedef struct { u16 type; u8 pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
    "OSPiHandle":   """\
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

    # FIX: Full OSPfs with all members referenced by source (queue, channel,
    # activebank, banks, dir_size, dir_table, inode_start_page).
    "OSPfs": """\
typedef struct OSPfs_s {
    struct OSIoMesg_s ioMesgBuf;
    struct OSMesgQueue_s *queue;
    s32 channel;
    u8 activebank;
    u8 banks;
    u8 status;
    u8 inodeTable[256];
    u8 dir[256];
    u8 dir_table[256];
    u32 dir_size;
    u32 inode_start_page;
    u32 label[8];
    s32 repairList[256];
    u32 version;
    u32 checksum;
    u32 inodeCacheIndex;
    u8 inodeCache[256];
} OSPfs;""",

    "OSTimer":   "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;",
    "LookAt":    "typedef struct { struct { float x, y, z; float pad; } l[2]; } LookAt;",
}

SDK_DEFINES_THESE = {"OSScTask"}
# NOTE: OSTask removed from SDK_DEFINES_THESE — it is NOT being provided by the
# SDK headers in the Android NDK build, so we must emit it ourselves.

PHASE_3_STRUCTS = {
    # FIX: Vtx — added Vtx_n (normal vector variant) to union so .n member works.
    "Vtx": """\
typedef struct {
    short ob[3];
    unsigned short flag;
    short tc[2];
    unsigned char cn[4];
} Vtx_t;
typedef struct {
    short ob[3];
    unsigned short flag;
    short tc[2];
    unsigned char cn[4];
} Vtx_n;
typedef union {
    Vtx_t v;
    Vtx_n n;
    long long int force_align[8];
} Vtx;""",

    # FIX: OSViMode — comRegs and fldRegs are structs with named fields so
    # vi*.c member accesses like mode->comRegs.ctrl, .width, .burst etc. work.
    # Using named struct members that match standard N64 SDK layout.
    "OSViMode": """\
#ifndef __OSViCommonRegs_DEFINED
#define __OSViCommonRegs_DEFINED
typedef struct {
    u32 ctrl;
    u32 width;
    u32 burst;
    u32 vSync;
} __OSViCommonRegs;
#endif
#ifndef __OSViFieldRegs_DEFINED
#define __OSViFieldRegs_DEFINED
typedef struct {
    u32 origin;
    u32 yScale;
    u32 vStart;
    u32 vBurst;
    u32 vIntr;
    u32 hStart;
    u32 xScale;
} __OSViFieldRegs;
#endif
typedef struct OSViMode_s {
    u32 type;
    __OSViCommonRegs comRegs;
    __OSViFieldRegs  fldRegs[2];
} OSViMode;""",

    "OSViContext": "typedef struct OSViContext_s { u16 state; u16 retraceCount; void *framep; struct OSViMode_s *modep; u32 control; struct OSMesgQueue_s *msgq; OSMesg msg; } OSViContext;",

    # FIX: OSTask — was wrongly in SDK_DEFINES_THESE; emit full body.
    "OSTask": """\
typedef struct {
    u32  type;
    u32  flags;
    u64 *ucode_boot;
    u32  ucode_boot_size;
    u64 *ucode;
    u32  ucode_size;
    u64 *ucode_data;
    u32  ucode_data_size;
    u64 *dram_stack;
    u32  dram_stack_size;
    u64 *output_buff;
    u64 *output_buff_size;
    u64 *data_ptr;
    u32  data_size;
    u64 *yield_data_ptr;
    u32  yield_data_size;
} OSTask_t;
typedef union {
    OSTask_t t;
    long long int force_align[16];
} OSTask;""",
}

N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

N64_OS_OPAQUE_TYPES = {
    "OSPfs", "OSContStatus", "OSContPad", "OSPiHandle", "OSMesgQueue", "OSThread",
    "OSIoMesg", "OSTimer", "OSScTask", "OSTask", "OSScClient", "OSScKiller",
    "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr", "OSPfsState", "OSPfsFile",
    "OSPfsDir", "OSDevMgr", "SPTask", "GBIarg",
    # FIX: added
    "OSYieldResult",
}

N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "INTERLEAVE_STATE",
    "ENVMIX_STATE2", "HIPASSLOOP_STATE", "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

# FIX: Removed os*ViMode globals and osRomBase/osTvType/osResetType/osAppNMIBuffer/osClockRate
# from extern-long-long treatment — they have real typed definitions in source files.
# Keeping only the pointer globals that truly need extern shims.
N64_KNOWN_GLOBALS = {
    "__osPiTable":       "struct OSPiHandle_s *__osPiTable;",
    "__osFlashHandle":   "struct OSPiHandle_s *__osFlashHandle;",
    "__osSfHandle":      "struct OSPiHandle_s *__osSfHandle;",
    "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
    "__osRunQueue":      "struct OSThread_s *__osRunQueue;",
    "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
    # FIX: OSHWIntr is u32 bitmask; __OSGlobalIntMask is the global instance
    "__OSGlobalIntMask": "OSHWIntr __OSGlobalIntMask;",
}

# Globals that the source defines with their own correct type — do NOT emit
# extern long long stubs for these, they will conflict.
_TYPED_SOURCE_GLOBALS = {
    "osTvType", "osRomBase", "osResetType", "osAppNMIBuffer",
    "osClockRate", "osViModeNtscLan1", "osViModePalLan1", "osViModeMpalLan1",
    "osPiRawStartDma", "osEPiRawStartDma",
}

# Standard math/string/stdlib functions — never emit stubs or protos for these.
_STDLIB_FUNCS = {
    "sinf", "cosf", "sqrtf", "tanf", "acosf", "asinf", "atanf", "atan2f",
    "sin", "cos", "sqrt", "tan", "acos", "asin", "atan", "atan2",
    "abs", "fabs", "fabsf", "pow", "powf", "floor", "floorf", "ceil", "ceilf",
    "round", "roundf", "fmod", "fmodf",
    "memcpy", "memset", "memmove", "memcmp",
    "strlen", "strcpy", "strncpy", "strcmp", "strncmp",
    "strcat", "strncat", "strchr", "strrchr", "strstr",
    "malloc", "calloc", "realloc", "free", "exit",
    "atoi", "atol", "atof", "strtol", "strtod",
    "rand", "srand", "printf", "fprintf", "sprintf", "snprintf",
}

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

/* FIX: OSHWIntr is a u32 bitmask, NOT a struct.
   Using it as struct causes binary operator and array-subscript failures. */
typedef u32   OSHWIntr;

/* FIX: ADPCM_STATE must decay to void* for alAdpcmDec/alLoadParam calls.
   Defining as short array typedef gives pointer-decay compatibility. */
#ifndef ADPCM_STATE_DEFINED
#define ADPCM_STATE_DEFINED
typedef short ADPCM_STATE[9];  /* ADPCMFSIZE = 9 */
#endif

/* FIX: OSYieldResult */
#ifndef OSYieldResult_DEFINED
#define OSYieldResult_DEFINED
typedef u32 OSYieldResult;
#endif

/* FIX: Vp (viewport) */
#ifndef Vp_DEFINED
#define Vp_DEFINED
typedef struct {
    s16 vscale[4];
    s16 vtrans[4];
} Vp_t;
typedef union {
    Vp_t v;
    long long int force_align[4];
} Vp;
#endif

#endif
"""

# n64_bool.h shim content — for include/core2/file.h which does #include "n64_bool.h"
_N64_BOOL_H_CONTENT = """\
#pragma once
/* n64_bool.h shim — provided by patch_engine for Android NDK build */
#ifndef n64_bool
typedef int n64_bool;
#endif
#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif
"""

# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------
def normalize_path(filepath: str) -> str:
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath: return filepath.split(marker)[-1]
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
        if in_auto_block and re.match(r'(?:typedef\s+)?(?:struct|union)\s+\w+(?:_s)?\s+\w+\s*;', s):
            continue
        in_auto_block = False
        result.append(line)
    return '\n'.join(result)

def _rename_posix_static(content: str, func_name: str, filepath: str) -> Tuple[str, bool]:
    prefix   = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define   = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content: return content, False
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
    if re.search(rf"\btypedef\s+(?:struct|union)\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content): return True
    if f"{tag}_DEFINED" in content: return True
    return False

def strip_redefinition(content: str, tag: str) -> str:
    """CRITICAL FIX: Safely strips out conflicting union AND struct definitions."""
    changed = True
    while changed:
        changed = False
        pattern1 = re.compile(rf"\b(?:struct|union)\s+{re.escape(tag)}\s*\{{")
        match = pattern1.search(content)
        if match:
            start_idx = match.start()
            pre = content[:start_idx].rstrip()
            if pre.endswith("typedef"): start_idx = pre.rfind("typedef")
            brace_idx = content.find('{', match.start())
            open_braces, curr_idx = 1, brace_idx + 1
            while curr_idx < len(content) and open_braces > 0:
                if content[curr_idx] == '{': open_braces += 1
                elif content[curr_idx] == '}': open_braces -= 1
                curr_idx += 1
            semi_idx = content.find(';', curr_idx)
            if semi_idx != -1:
                content = content[:start_idx] + f"/* AUTO-STRIPPED RE-DEF: {tag} */\n" + content[semi_idx+1:]
                changed = True; continue

        idx = 0
        while True:
            match = re.search(r"\btypedef\s+(?:struct|union)\b[^{]*\{", content[idx:])
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
                    changed = True; break
                idx = semi_idx + 1
            else:
                idx = curr_idx + 1
        if changed: continue

        c_new, n = re.subn(rf"\btypedef\s+(?:struct\s+|union\s+)?[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;", f"/* STRIPPED LOOSE TYPEDEF: {tag} */", content)
        if n > 0: content, changed = c_new, True
        c_new, n = re.subn(rf"\b(?:struct|union)\s+{re.escape(tag)}\s*;", f"/* STRIPPED FWD DECL: {tag} */", content)
        if n > 0: content, changed = c_new, True
    return content

def repair_unterminated_conditionals(content: str) -> str:
    lines = content.split('\n')
    stack = []
    output = list(lines)
    remove = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'#\s*(?:ifndef|ifdef|if)\b', stripped): stack.append(i)
        elif re.match(r'#\s*endif\b', stripped):
            if stack: stack.pop()
    for idx in stack:
        remove.add(idx)
        for j in range(idx + 1, min(idx + 4, len(lines))):
            if lines[j].strip().startswith('#define') or lines[j].strip().startswith('#endif'):
                remove.add(j); break
    if not remove: return content
    result = [line for i, line in enumerate(output) if i not in remove]
    return '\n'.join(result)

def clean_conflicting_typedefs():
    if not os.path.exists(TYPES_HEADER): return
    content = original = read_file(TYPES_HEADER)
    # FIX: also strip any stale OSHWIntr struct definition if present
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg", "OSHWIntr"]:
        content = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s+{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
    if content != original: write_file(TYPES_HEADER, content)

def ensure_types_header_base() -> str:
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content: content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
    # FIX: extended cleanup list to include OSHWIntr and ADPCM_STATE
    for p in ["u8","s8","u16","s16","u32","s32","u64","s64","f32","f64","n64_bool",
              "OSIntMask","OSTime","OSId","OSPri","OSMesg","OSHWIntr"]:
        content = re.sub(rf"\btypedef\s+[^;]+\b{re.escape(p)}\s*;", "", content)
    for p in ["OSIntMask","OSTime","OSId","OSPri","OSMesg","OSHWIntr"]:
        content = re.sub(rf"(?:typedef\s+)?(?:struct\s+|union\s+)?{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(p)}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s+{re.escape(p)}(?:_s)?\s+{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"(?:struct|union)\s+{re.escape(p)}(?:_s)?\s*;\n?", "", content)

    content = content.replace("#pragma once", f"#pragma once\n{_CORE_PRIMITIVES}", 1)

    # FIX: Wrap extern C++ guards around the known-globals block to prevent
    # "different language linkage" errors when the header is included from .cpp files.
    extern_c_guard = '\n#ifdef __cplusplus\nextern "C" {\n#endif\n'
    extern_c_end   = '\n#ifdef __cplusplus\n}\n#endif\n'
    if extern_c_guard not in content:
        content += extern_c_guard + extern_c_end

    content = repair_unterminated_conditionals(content)
    write_file(TYPES_HEADER, content)

    # FIX: Emit n64_bool.h shim into the NDK sysroot include search path.
    # Best effort: place alongside n64_types.h so it is found by relative include.
    _emit_n64_bool_h()

    return content

def _emit_n64_bool_h():
    """Emit n64_bool.h shim next to n64_types.h and in include/core2/ if present."""
    shim_locations = [
        os.path.join(os.path.dirname(TYPES_HEADER), "n64_bool.h"),
    ]
    # Also try to find include/core2/ relative to project root
    for candidate in ["include/core2/n64_bool.h", "Android/app/src/main/cpp/../../../../../include/core2/n64_bool.h"]:
        if os.path.isdir(os.path.dirname(candidate)):
            shim_locations.append(candidate)
    for path in shim_locations:
        if not os.path.exists(path):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                write_file(path, _N64_BOOL_H_CONTENT)
            except Exception:
                pass

def _scrape_logs_into_categories(categories: dict) -> None:
    log_candidates = ["Android/failed_files.log", "Android/full_build_log.txt", "full_build_log.txt", "build_log.txt", "Android/build_log.txt"]
    for f in os.listdir("."):
        if f.endswith((".txt", ".log")): log_candidates.append(f)

    for key in ["missing_types","posix_reserved_conflict","struct_redef","typedef_redef"]:
        categories.setdefault(key, [])
        if isinstance(categories[key], set): categories[key] = list(categories[key])

    for key in ["undeclared_identifiers","implicit_func_stubs","need_struct_body","not_a_pointer", "errno_conflict"]:
        categories.setdefault(key, set())
        if isinstance(categories[key], list): categories[key] = set(categories[key])

    mt  = categories["missing_types"]
    pc  = categories["posix_reserved_conflict"]
    sr  = categories["struct_redef"]
    ui  = categories["undeclared_identifiers"]
    ifs = categories["implicit_func_stubs"]
    nsb = categories["need_struct_body"]
    nap = categories["not_a_pointer"]
    err = categories["errno_conflict"]

    for log_file in set(log_candidates):
        if not os.path.exists(log_file): continue
        content = read_file(log_file)

        # Scrape Errno failures
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:.*errno", content):
            err.add(normalize_path(m.group(1)))
        if "errno -> ->errnum" in content:
            for f in os.listdir("."):
                if f.endswith(('.c', '.cpp', '.h')): err.add(f)

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+unknown type name '(\w+)'", content):
            filepath, tag = normalize_path(m.group(1)), m.group(2)
            if not any(isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag for x in mt): mt.append((filepath, tag))
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            tag = m.group(1)
            if not any((isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag) or x==tag for x in mt): mt.append(tag)
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+static declaration of '(\w+)' follows non-static declaration", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in pc: pc.append(entry)
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+redefinition of '(\w+)'", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in sr: sr.append(entry)

        # FIX: scrape "typedef redefinition with different types ('struct X' vs 'struct Y')"
        for m in re.finditer(
            r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+"
            r"error:\s+typedef redefinition with different types \('struct ([A-Za-z0-9_]+)' vs 'struct ([A-Za-z0-9_]+)'\)",
            content
        ):
            filepath = normalize_path(m.group(1))
            tag1, tag2 = m.group(2), m.group(3)
            entry = (filepath, f"struct {tag1}", f"struct {tag2}")
            categories.setdefault("typedef_redef", [])
            if entry not in categories["typedef_redef"]: categories["typedef_redef"].append(entry)

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+typedef redefinition.*?vs '(?:struct|union )?(\w+)'", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in sr: sr.append(entry)
        for m in re.finditer(r"n64_types\.h:\d+:\d+:\s+error:\s+typedef redefinition.*?'(?:struct|union )?(\w+)'", content): nsb.add(m.group(1))
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+use of undeclared identifier '(\w+)'", content): ui.add(m.group(2))
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+implicit declaration of function '(\w+)'", content): ifs.add(m.group(2))
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+member access into incomplete type '(?:struct|union )?(\w+)'", content): nsb.add(m.group(2))
        for m in re.finditer(r"error:\s+member reference (?:base )?type '.*?' is not a (?:pointer|structure or union)\n([^\n]+)\n", content):
            snippet = m.group(1)
            for mm in re.finditer(r'([A-Za-z0-9_]+)(?:->|\.)', snippet): nap.add(mm.group(1))
        for m in re.finditer(r"error:\s+subscript of pointer to incomplete type '(?:struct|union )?(\w+)'", content): nsb.add(m.group(1))
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+redeclaration of '(\w+)' with a different type", content):
            filepath, var = normalize_path(m.group(1)), m.group(2)
            categories.setdefault("type_mismatch_globals", [])
            if (filepath, var) not in categories["type_mismatch_globals"]: categories["type_mismatch_globals"].append((filepath, var))

        # FIX: scrape "redefinition of 'X' with a different type: 'T1' vs 'T2'"
        # for typed globals (osTvType, osRomBase, osViMode*, osClockRate, etc.)
        # — add them to type_mismatch_globals so stale extern long long stubs get removed.
        for m in re.finditer(
            r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+"
            r"error:\s+redefinition of '([A-Za-z0-9_]+)' with a different type",
            content
        ):
            filepath, var = normalize_path(m.group(1)), m.group(2)
            if var in _TYPED_SOURCE_GLOBALS:
                categories.setdefault("type_mismatch_globals", [])
                if (filepath, var) not in categories["type_mismatch_globals"]:
                    categories["type_mismatch_globals"].append((filepath, var))

        # FIX: scrape "redefinition of 'X' as different kind of symbol"
        # (osPiRawStartDma, osEPiRawStartDma) — same treatment.
        for m in re.finditer(
            r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+"
            r"error:\s+redefinition of '([A-Za-z0-9_]+)' as different kind of symbol",
            content
        ):
            filepath, var = normalize_path(m.group(1)), m.group(2)
            if var in _TYPED_SOURCE_GLOBALS:
                categories.setdefault("type_mismatch_globals", [])
                if (filepath, var) not in categories["type_mismatch_globals"]:
                    categories["type_mismatch_globals"].append((filepath, var))

        # FIX: scrape "no member named 'X' in 'struct Y'" — feeds missing_members
        for m in re.finditer(
            r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+"
            r"error:\s+no member named '([A-Za-z0-9_]+)' in 'struct ([A-Za-z0-9_]+)'",
            content
        ):
            filepath = normalize_path(m.group(1))
            member, struct_name = m.group(2), m.group(3)
            # Strip trailing _s for lookup key
            base = struct_name[:-2] if struct_name.endswith("_s") else struct_name
            categories.setdefault("missing_members", [])
            entry = (base, member)
            if entry not in categories["missing_members"]: categories["missing_members"].append(entry)

        # FIX: "no member named 'n' in 'Vtx'" — ensure Vtx goes into need_struct_body
        for m in re.finditer(r"error:\s+no member named '(\w+)' in 'Vtx'", content):
            nsb.add("Vtx")

        # FIX: "declaration of 'X' has a different language linkage" — collect for
        # extern-C guard audit (math functions must not have stubs injected)
        for m in re.finditer(r"error:\s+declaration of '([A-Za-z0-9_]+)' has a different language linkage", content):
            func = m.group(1)
            # If it's a stdlib function, just record for removal from stubs
            categories.setdefault("linkage_conflict_funcs", set())
            categories["linkage_conflict_funcs"].add(func)

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
        if k not in SDK_DEFINES_THESE: ACTIVE_STRUCTS[k] = v

    if intelligence_level >= 2:
        for tag in ACTIVE_STRUCTS.keys(): categories.setdefault("need_struct_body", set()).add(tag)
        # FIX: OSTask is no longer in SDK_DEFINES_THESE, so always inject it
        categories.setdefault("need_struct_body", set()).add("OSTask")

    _scrape_logs_into_categories(categories)
    clean_conflicting_typedefs()
    types_content = ensure_types_header_base()

    # ------------------------------------------------------------------
    # NATIVE ERRNO SANITIZER
    # ------------------------------------------------------------------
    if categories.get("errno_conflict"):
        for filepath in categories["errno_conflict"]:
            if os.path.exists(filepath):
                original_content = read_file(filepath)
                new_content = re.sub(r'->errno\b', '->errnum', original_content)
                new_content = re.sub(r'\.errno\b', '.errnum', new_content)
                if original_content != new_content:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath)
                    fixes += 1

    # ------------------------------------------------------------------
    # FIX: Remove stubs/protos for functions with linkage conflicts
    # (sinf, cosf, sqrtf, __osRunQueue, __osFaultedThread language linkage)
    # ------------------------------------------------------------------
    if categories.get("linkage_conflict_funcs"):
        types_content = read_file(TYPES_HEADER)
        changed = False
        for func in categories["linkage_conflict_funcs"]:
            if func in _STDLIB_FUNCS:
                # Remove any injected extern proto for stdlib functions
                types_content, n = re.subn(
                    rf"(?m)^#ifndef {re.escape(func)}_DEFINED\n.*?#define {re.escape(func)}_DEFINED\nextern[^\n]+{re.escape(func)}[^\n]*\n#endif\n?",
                    "", types_content, flags=re.DOTALL
                )
                types_content, n2 = re.subn(
                    rf"(?m)^extern\s+long\s+long\s+int\s+{re.escape(func)}\s*\(\s*\)\s*;\n?",
                    "", types_content
                )
                if n + n2 > 0: changed = True
        if changed: write_file(TYPES_HEADER, types_content); fixes += 1

    if intelligence_level >= 2:
        original_types = types_content
        scrub_targets = (set(ACTIVE_STRUCTS.keys()) | N64_OS_OPAQUE_TYPES | set(ACTIVE_MACROS.keys()) |
                         {"__osPiTable","__OSBlockInfo","__OSTranxInfo","__osCurrentThread","__osRunQueue","__osFaultedThread"} |
                         _TYPED_SOURCE_GLOBALS)
        for target in scrub_targets:
            types_content = re.sub(rf"(?m)^#ifndef {re.escape(target)}_DEFINED\n#define {re.escape(target)}_DEFINED\nextern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?;\n#endif\n?", "", types_content)
            types_content = re.sub(rf"(?m)^extern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?;\n?", "", types_content)
        if types_content != original_types:
            write_file(TYPES_HEADER, types_content); fixes += 1

        # FIX: Ensure extern "C" block wraps the known globals to fix C++ linkage errors.
        types_content = read_file(TYPES_HEADER)
        extern_c_guard = '\n#ifdef __cplusplus\nextern "C" {\n#endif\n'
        extern_c_end   = '\n#ifdef __cplusplus\n}\n#endif\n'
        globals_block  = ""
        globals_added  = False
        for glob, decl in N64_KNOWN_GLOBALS.items():
            if glob not in types_content:
                globals_block += f"#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {decl}\n#endif\n"
                globals_added = True
        if globals_added:
            types_content += extern_c_guard + globals_block + extern_c_end
            write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("type_mismatch_globals"):
        types_content = read_file(TYPES_HEADER)
        changed = False
        for item in categories["type_mismatch_globals"]:
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            _, var = item[0], item[1]
            types_content = re.sub(rf"(?m)^#ifndef {re.escape(var)}_DEFINED\n.*?#define {re.escape(var)}_DEFINED\nextern[^\n]+{re.escape(var)}[^\n]*\n#endif\n?", "", types_content, flags=re.DOTALL)
            types_content = re.sub(rf"(?m)^extern[^\n]+\b{re.escape(var)}\b[^\n]*\n?", "", types_content)
            changed = True
            # FIX: Only re-add from N64_KNOWN_GLOBALS, never re-add _TYPED_SOURCE_GLOBALS
            if var in N64_KNOWN_GLOBALS and var not in _TYPED_SOURCE_GLOBALS and f"{var}_DEFINED" not in types_content:
                decl = N64_KNOWN_GLOBALS[var]
                types_content += f"\n#ifndef {var}_DEFINED\n#define {var}_DEFINED\nextern {decl}\n#endif\n"
        if changed: write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # ZERO-MACRO ASSASSIN
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
    known_type_tags.update(N64_AUDIO_STATE_TYPES)

    macros_cleaned = False
    for tag in known_type_tags:
        p1 = rf"(?m)^\s*#ifndef {re.escape(tag)}\s*\n\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(p1, "", types_content)
        p2 = rf"(?m)^\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
        types_content, n2 = re.subn(p2, "", types_content)
        p3 = rf"(?m)^\s*#ifndef {re.escape(tag)}\s*\n\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNDECLARED IDENTIFIER \*/\s*\n\s*#endif\s*\n?"
        types_content, n3 = re.subn(p3, "", types_content)
        if n1 + n2 + n3 > 0: macros_cleaned = True; fixes += 1
    if macros_cleaned: write_file(TYPES_HEADER, types_content)

    if categories.get("not_a_pointer"):
        types_content = read_file(TYPES_HEADER)
        changed = False
        for member in sorted(categories["not_a_pointer"]):
            if not isinstance(member, str): continue
            new_types, n = re.subn(rf"\blong\s+long\s+int\s+{re.escape(member)}\s*;", f"void* {member}; /* AUTO-FIX: cast to pointer */", types_content)
            if n > 0: types_content = new_types; changed = True
        if changed: write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("implicit_func_stubs"):
        types_content = read_file(TYPES_HEADER)
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
        stubs_content = read_file(STUBS_FILE)
        funcs_added = False
        for func in sorted(categories["implicit_func_stubs"]):
            # FIX: never emit stubs for stdlib/math functions — causes linkage conflicts
            if not isinstance(func,str) or func in _STDLIB_FUNCS: continue
            proto = f"long long int {func}();"
            if proto not in types_content:
                types_content += f"\n#ifndef {func}_DEFINED\n#define {func}_DEFINED\nextern {proto}\n#endif\n"; funcs_added = True
            impl = f"long long int {func}() {{ return 0; }}\n"
            if impl not in stubs_content: stubs_content += impl; funcs_added = True
        if funcs_added:
            write_file(TYPES_HEADER, types_content); write_file(STUBS_FILE, stubs_content); fixes += 1

    if categories.get("undeclared_identifiers"):
        types_content = read_file(TYPES_HEADER)
        idents_added = False
        for ident in sorted(categories["undeclared_identifiers"]):
            if not isinstance(ident, str) or ident in N64_KNOWN_GLOBALS: continue
            # FIX: skip _TYPED_SOURCE_GLOBALS and stdlib names
            if ident in _TYPED_SOURCE_GLOBALS or ident in _STDLIB_FUNCS: continue
            if ident in ACTIVE_MACROS:
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} {ACTIVE_MACROS[ident]}\n#endif\n"; idents_added = True
                continue
            if ident.isupper() or ident.startswith(("G_","OS_","PI_","PFS_","LEO_","ADPCM","UNITY","MAX_")):
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* AUTO-INJECTED UNDECLARED IDENTIFIER */\n#endif\n"; idents_added = True
            else:
                decl = f"extern long long int {ident};"
                if decl not in types_content and f"{ident}_DEFINED" not in types_content:
                    types_content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\n{decl}\n#endif\n"; idents_added = True
        if idents_added: write_file(TYPES_HEADER, types_content); fixes += 1

    for type_name in sorted(categories.get("conflict_typedef", [])):
        if type_name in SDK_DEFINES_THESE: continue
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(?:typedef\s+)?(?:struct\s+|union\s+)?{re.escape(type_name)}\s*\{{[^}}]*\}}\s*{re.escape(type_name)}?\s*;\n?"
        new_types, n = re.subn(pattern, "", types_content)
        new_types = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int)\s+{re.escape(type_name)}\s*;", "", new_types)
        if n > 0:
            if f"struct {type_name}_s {{" not in new_types: new_types += f"\nstruct {type_name}_s {{ long long int force_align[64]; }};\n"
            write_file(TYPES_HEADER, new_types); types_content = new_types; fixes += 1

    array_names = {"id","label","name","buffer","data","str","string","temp"}
    for item in sorted(categories.get("missing_members", [])):
        if not isinstance(item,(list,tuple)) or len(item)<2: continue
        struct_name, member_name = item[0], item[1]
        # FIX: If the struct has a full body in ACTIVE_STRUCTS or _N64_OS_STRUCT_BODIES,
        # do NOT inject stray fields — add it to need_struct_body so the correct full
        # body replaces any stale opaque stub.
        all_bodies = {**_N64_OS_STRUCT_BODIES, **PHASE_3_STRUCTS}
        if struct_name in all_bodies:
            categories.setdefault("need_struct_body", set()).add(struct_name)
            continue
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
            if n > 0: write_file(TYPES_HEADER, new_types); fixes += 1
        else:
            mn = member_name
            field = (f"unsigned char {mn}[128];" if mn in array_names else f"void* {mn};" if any(x in mn.lower() for x in ["ptr","func","cb"]) else f"long long int {mn};")
            types_content += f"\nstruct {struct_name} {{\n    {field}\n    long long int force_align[64];\n}};\n"
            write_file(TYPES_HEADER, types_content); fixes += 1

    for item in sorted(categories.get("redefinition", [])):
        if not isinstance(item,(list,tuple)) or len(item)<2: continue
        filepath, var = item[0], item[1]
        if os.path.exists(filepath):
            content = read_file(filepath)
            new_content, n = re.subn(rf"^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */", content, flags=re.MULTILINE)
            if n > 0: write_file(filepath, new_content); fixed_files.add(filepath); fixes += 1

    # CRITICAL FIX: Add _s logic securely to audio and missing tags
    for item in sorted(categories.get("missing_types", []), key=str):
        if isinstance(item,(list,tuple)) and len(item)>=2: filepath, tag = item[0], item[1]
        elif isinstance(item, str): filepath, tag = None, item
        else: continue
        if not isinstance(tag, str) or tag in SDK_DEFINES_THESE: continue

        types_content = read_file(TYPES_HEADER)
        if tag in N64_PRIMITIVES: pass
        elif tag in N64_AUDIO_STATE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};\n#endif\n"
                write_file(TYPES_HEADER, types_content); fixes += 1
        elif tag in ACTIVE_STRUCTS: categories.setdefault("need_struct_body", set()).add(tag)
        elif tag in N64_OS_OPAQUE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += "\n" + _opaque_stub(tag, size=64); write_file(TYPES_HEADER, types_content); fixes += 1
        else:
            if not re.search(rf"\b{re.escape(tag)}\b", types_content):
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content); fixed_files.add(TYPES_HEADER); fixes += 1

        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c); fixed_files.add(filepath); fixes += 1

    if categories.get("unknown_audio_state_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        for t in sorted(categories["unknown_audio_state_types"]):
            if not isinstance(t,str) or t not in N64_AUDIO_STATE_TYPES: continue
            if not _type_already_defined(t, types_content):
                types_content += f"\n#ifndef {t}_DEFINED\n#define {t}_DEFINED\ntypedef struct {t}_s {{ long long int force_align[64]; }} {t};\n#endif\n"; added = True
        if added: write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("extraneous_brace"):
        types_content = read_file(TYPES_HEADER)
        original = types_content
        types_content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", types_content)
        types_content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", types_content)
        if types_content != original: write_file(TYPES_HEADER, types_content); fixes += 1

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
                write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    for item in sorted(categories.get("missing_n64_types",[]), key=str):
        filepath = item if isinstance(item,str) else str(item)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'n64_types.h"' not in content and '<n64_types.h>' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content); fixed_files.add(filepath); fixes += 1

    for item in sorted(categories.get("actor_pointer",[]), key=str):
        filepath = item if isinstance(item,str) else str(item)
        if not os.path.exists(filepath): continue
        content = original = read_file(filepath)
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original: write_file(filepath, content); fixed_files.add(filepath); fixes += 1

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
            if fwd_lines: write_file(filepath, "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n" + content); fixed_files.add(filepath); fixes += 1

    fixd_files: set = set()
    for item in categories.get("typedef_redef",[]):
        if isinstance(item,(list,tuple)) and len(item)>=1: fixd_files.add(item[0])
    for item in categories.get("struct_redef",[]):
        if isinstance(item,(list,tuple)) and len(item)>=1: fixd_files.add(item[0])

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content  = read_file(filepath); original = content; content  = strip_auto_preamble(content)
        for item in categories.get("struct_redef",[]):
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            fp2, tag = item[0], item[1]
            if fp2 != filepath or tag in SDK_DEFINES_THESE: continue
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
                else: content, _ = re.subn(r"\bstruct\s+" + re.escape(alias) + r"\b", f"struct {target_tag}", content)

        if content != original: write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False; seen: set = set()
        for item in categories["incomplete_sizeof"]:
            if not isinstance(item,(list,tuple)) or len(item)<2: continue
            filepath, tag = item[0], item[1]
            if tag in seen or tag in SDK_DEFINES_THESE: continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in ACTIVE_STRUCTS: continue
            is_sdk = (tag.isupper() or tag.startswith(("OS","SP","DP","AL","GU","G_")) or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"; types_added = True
        if types_added: write_file(TYPES_HEADER, types_content); fixes += 1

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
                if changed: write_file(filepath, new_content); fixed_files.add(filepath); fixes += 1
                continue
            prefix    = os.path.basename(filepath).split('.')[0]
            macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
            if macro_fix not in content:
                anchor  = '#include "ultra/n64_types.h"'
                content = (content.replace(anchor, anchor + macro_fix) if anchor in content else macro_fix + content)
                write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    if categories.get("undeclared_macros"):
        types_content = read_file(TYPES_HEADER)
        macros_added  = False
        for macro in sorted(categories["undeclared_macros"]):
            if not isinstance(macro, str): continue
            if macro in KNOWN_FUNCTION_MACROS:
                defn = KNOWN_FUNCTION_MACROS[macro]
                if defn not in types_content: types_content += f"\n{defn}\n"; macros_added = True
            elif macro in ACTIVE_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {ACTIVE_MACROS[macro]}\n#endif\n"; macros_added = True
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"; macros_added = True
        if macros_added: write_file(TYPES_HEADER, types_content); fixes += 1

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
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}"); includes_added = True
        # FIX: math.h inclusion must be inside extern "C" to avoid linkage conflict.
        # Instead of injecting into n64_types.h (a forced C include), emit a wrapper.
        # Suppress the direct #include <math.h> if it was added — it causes linkage errors
        # in C++ TUs. The math functions come from libc++ automatically.
        if includes_added:
            types_content = re.sub(r"#pragma once\n#include <math\.h>", "#pragma once", types_content)
            types_content = re.sub(r"(?m)^#include <math\.h>\n", "", types_content)
            write_file(TYPES_HEADER, types_content)

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
            if not isinstance(sym, str) or sym.startswith("_Z") or "vtable" in sym: continue
            # FIX: do not stub stdlib functions
            if sym in _STDLIB_FUNCS: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"; stubs_added = True
        if stubs_added: write_file(STUBS_FILE, existing_stubs); fixes += 1

    if categories.get("audio_states"):
        types_content = read_file(TYPES_HEADER)
        audio_added   = False
        for t in sorted(categories["audio_states"]):
            if not isinstance(t, str): continue
            if not _type_already_defined(t, types_content):
                types_content += f"\n#ifndef {t}_DEFINED\n#define {t}_DEFINED\ntypedef struct {t}_s {{ long long int force_align[32]; }} {t};\n#endif\n"; audio_added = True
        if audio_added: write_file(TYPES_HEADER, types_content); fixes += 1

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
                if not _type_already_defined(t, types_content): types_content += "\n" + _opaque_stub(t); k_added = True
            elif not re.search(rf"\b{re.escape(t)}\b", types_content):
                struct_tag = f"{t}_s" if not t.endswith("_s") else t
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {t};\n"
                types_content += f"\n#ifndef {t}_DEFINED\n#define {t}_DEFINED\n{decl}#endif\n"; k_added = True
            if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                c = read_file(filepath)
                if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + c); fixed_files.add(filepath); fixes += 1
        if k_added: write_file(TYPES_HEADER, types_content); fixes += 1

        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs); fixes += 1

    if categories.get("undeclared_gbi"):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if not isinstance(ident, str): continue
            if ident in ACTIVE_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {ACTIVE_MACROS[ident]}\n#endif\n"; gbi_added = True
            elif ident not in ACTIVE_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"; gbi_added = True
        if gbi_added: write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added  = False
        ordered_tags = [t for t in ACTIVE_STRUCTS.keys() if t in categories.get("need_struct_body", set()) and t not in SDK_DEFINES_THESE]
        other_tags   = sorted([t for t in categories.get("need_struct_body", set()) if t not in ACTIVE_STRUCTS and t not in SDK_DEFINES_THESE])

        for tag in ordered_tags + other_tags:
            if not isinstance(tag, str): continue
            body = ACTIVE_STRUCTS.get(tag)
            if not body:
                if tag in N64_OS_OPAQUE_TYPES and not _type_already_defined(tag, types_content):
                    types_content += "\n" + _opaque_stub(tag); bodies_added = True
                continue

            norm_body  = re.sub(r'\s+', ' ', body).strip(); norm_types = re.sub(r'\s+', ' ', types_content)
            if norm_body in norm_types: continue

            types_content = strip_redefinition(types_content, tag)
            if not tag.endswith("_s"): types_content = strip_redefinition(types_content, f"{tag}_s")

            # Explicitly strip sub-types that get collided
            if tag == "OSPiHandle":
                types_content = strip_redefinition(types_content, "__OSBlockInfo"); types_content = strip_redefinition(types_content, "__OSTranxInfo")
            if tag == "Vtx":
                types_content = strip_redefinition(types_content, "Vtx_t")
                types_content = strip_redefinition(types_content, "Vtx_n")
            if tag == "OSThread":
                types_content = strip_redefinition(types_content, "__OSThreadContext")
                types_content = re.sub(r"(?m)^typedef union __OSThreadContext_u[^;]+;\n?", "", types_content, flags=re.DOTALL)
            if tag == "OSViMode":
                types_content = strip_redefinition(types_content, "__OSViCommonRegs")
                types_content = strip_redefinition(types_content, "__OSViFieldRegs")
            if tag == "OSTask":
                types_content = strip_redefinition(types_content, "OSTask_t")

            types_content = re.sub(rf"#ifndef {re.escape(tag)}_DEFINED[\s\S]*?#endif\n?", "", types_content)
            if tag == "LookAt":
                types_content = re.sub(r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__Light_t\s*;\n?", "", types_content); types_content = re.sub(r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__LookAtDir\s*;\n?", "", types_content)
            if tag == "Mtx": types_content = re.sub(r"(?m)^typedef\s+union\s*\{[^}]*\}\s*__Mtx_data\s*;\n?", "", types_content)

            types_content += "\n" + body + "\n"; bodies_added = True

        if bodies_added:
            types_content = repair_unterminated_conditionals(types_content); write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("local_fwd_only"):
        file_to_types2: dict = defaultdict(set)
        for item in categories["local_fwd_only"]:
            if isinstance(item,(list,tuple)) and len(item)>=2: file_to_types2[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types2.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath); content = strip_auto_preamble(content); changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+(?:struct|union)[^{{]*\{{[^}}]*\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
                fwd_decl = f"typedef struct {t}_s {t};"
                fwd = f"/* AUTO: forward decl for type defined below */\n{fwd_decl}\n" if re.search(body_pattern, content) else f"/* AUTO: forward declarations */\n{fwd_decl}\n"
                if fwd_decl not in content: content = fwd + content; changed = True
            if changed: write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    if categories.get("missing_globals"):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for item in sorted(categories["missing_globals"], key=str):
            if isinstance(item,(list,tuple)) and len(item)>=2: _, glob = item[0], item[1]
            elif isinstance(item, str): glob = item
            else: continue
            if glob == "actor": continue
            # FIX: never add extern stubs for typed source globals
            if glob in _TYPED_SOURCE_GLOBALS: continue
            if glob in N64_KNOWN_GLOBALS:
                if f"{glob}_DEFINED" not in types_content: types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {N64_KNOWN_GLOBALS[glob]}\n#endif\n"; globals_added = True
            elif f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content:
                decl = (f"extern void* {glob};" if glob.endswith(("_ptr","_p")) else f"extern long long int {glob};")
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"; globals_added = True
        if globals_added: write_file(TYPES_HEADER, types_content); fixes += 1

    return fixes, fixed_files
