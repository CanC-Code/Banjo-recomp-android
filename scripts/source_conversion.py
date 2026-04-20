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

SYNTH_INTERNALS_H = "Android/app/src/main/cpp/../../../../../include/synthInternals.h"
SYNTH_INTERNALS_H_ALT = "include/synthInternals.h"

# ---------------------------------------------------------------------------
# Constants & Fallbacks
# ---------------------------------------------------------------------------
try:
    from error_parser import (
        BRACE_MATCH, N64_STRUCT_BODIES as _EP_STRUCTS, KNOWN_MACROS as _EP_MACROS,
        KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, OPAQUE_TYPES as _EP_OPAQUE,
        read_file as _ep_read, write_file as _ep_write,
    )
    read_file  = _ep_read
    write_file = _ep_write
except ImportError:
    BRACE_MATCH = r"[^{}]*"
    _EP_STRUCTS = {}
    _EP_MACROS  = {}
    _EP_OPAQUE  = set()

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
            with open(filepath, 'w', encoding='utf-8') as f:
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
# Core Primitives & Declarations
# ---------------------------------------------------------------------------
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
    "sched_yield",
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
typedef u32   OSIntMask;
typedef u64   OSTime;
typedef u32   OSId;
typedef s32   OSPri;
typedef void* OSMesg;
typedef u32   OSHWIntr;
#ifndef ADPCM_STATE_DEFINED
#define ADPCM_STATE_DEFINED
typedef short ADPCM_STATE[9];
#endif
#ifndef OSYieldResult_DEFINED
#define OSYieldResult_DEFINED
typedef u32 OSYieldResult;
#endif
#ifndef OSEvent_DEFINED
#define OSEvent_DEFINED
typedef u32 OSEvent;
#endif
#ifndef Vp_DEFINED
#define Vp_DEFINED
typedef struct { s16 vscale[4]; s16 vtrans[4]; } Vp_t;
typedef union { Vp_t vp; long long int force_align[4]; } Vp;
#endif
#ifdef __cplusplus
extern "C" int sched_yield(void);
#endif
#endif /* END_CORE_PRIMITIVES */
"""

_AUDIO_STATE_PREAMBLE = """\
/* AUTO-INJECTED by patch_engine.py: N64 audio DSP state forward typedefs */
#ifndef N64_AUDIO_STATES_DEFINED
#define N64_AUDIO_STATES_DEFINED
#ifndef RESAMPLE_STATE_DEFINED
#define RESAMPLE_STATE_DEFINED
typedef struct RESAMPLE_STATE_s { long long int force_align[64]; } RESAMPLE_STATE;
#endif
#ifndef POLEF_STATE_DEFINED
#define POLEF_STATE_DEFINED
typedef struct POLEF_STATE_s { long long int force_align[64]; } POLEF_STATE;
#endif
#ifndef ENVMIX_STATE_DEFINED
#define ENVMIX_STATE_DEFINED
typedef struct ENVMIX_STATE_s { long long int force_align[64]; } ENVMIX_STATE;
#endif
#ifndef INTERLEAVE_STATE_DEFINED
#define INTERLEAVE_STATE_DEFINED
typedef struct INTERLEAVE_STATE_s { long long int force_align[64]; } INTERLEAVE_STATE;
#endif
#ifndef ENVMIX_STATE2_DEFINED
#define ENVMIX_STATE2_DEFINED
typedef struct ENVMIX_STATE2_s { long long int force_align[64]; } ENVMIX_STATE2;
#endif
#ifndef HIPASSLOOP_STATE_DEFINED
#define HIPASSLOOP_STATE_DEFINED
typedef struct HIPASSLOOP_STATE_s { long long int force_align[64]; } HIPASSLOOP_STATE;
#endif
#ifndef COMPRESS_STATE_DEFINED
#define COMPRESS_STATE_DEFINED
typedef struct COMPRESS_STATE_s { long long int force_align[64]; } COMPRESS_STATE;
#endif
#ifndef REVERB_STATE_DEFINED
#define REVERB_STATE_DEFINED
typedef struct REVERB_STATE_s { long long int force_align[64]; } REVERB_STATE;
#endif
#ifndef MIXER_STATE_DEFINED
#define MIXER_STATE_DEFINED
typedef struct MIXER_STATE_s { long long int force_align[64]; } MIXER_STATE;
#endif
#endif /* N64_AUDIO_STATES_DEFINED */
"""

# ---------------------------------------------------------------------------
# Strict Dependency Graph Dictionaries
# ---------------------------------------------------------------------------
_ALL_STRUCTS = {
    "Mtx": "typedef union { long m[4][4]; struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;",
    "OSContStatus": "typedef struct OSContStatus_s { u16 type; u8 status; u8 errnum; } OSContStatus;",
    "OSContPad": "typedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; u8 errnum; } OSContPad;",
    "__OSThreadContext": "typedef union __OSThreadContext_u { u64 raw[67]; struct { u64 at, v0, v1, a0, a1, a2, a3; u64 t0, t1, t2, t3, t4, t5, t6, t7; u64 s0, s1, s2, s3, s4, s5, s6, s7; u64 t8, t9; u64 gp, sp, s8, ra; u64 lo, hi; u32 sr, fpcsr, rcp; u64 pc; u64 fp[32]; }; } __OSThreadContext;",
    "OSThread": "struct OSThread_s; typedef struct OSThread_s { struct OSThread_s *next; OSPri priority; struct OSThread_s **queue; struct OSThread_s *tlnext; u16 state; u16 flags; OSId id; int fp; __OSThreadContext context; } OSThread;",
    "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; s32 validCount; s32 first; s32 msgCount; OSMesg *msg; } OSMesgQueue;",
    "OSMesgHdr": "typedef struct { u16 type; u8 pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
    "__OSBlockInfo": "typedef struct { u32 errStatus; void *dramAddr; void *C2Addr; u32 sectorSize; u32 C1ErrNum; u32 C1ErrSector[4]; } __OSBlockInfo;",
    "__OSTranxInfo": "typedef struct { u32 cmdType; u16 transferMode; u16 blockNum; s32 sectorNum; u32 devAddr; u32 bmCtlShadow; u32 seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;",
    "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; u8 type; u8 latency; u8 pageSize; u8 relDuration; u8 pulse; u8 domain; u32 baseAddress; u32 speed; __OSTranxInfo transferInfo; } OSPiHandle;",
    "OSIoMesg": "typedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; u32 devAddr; u32 size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
    "OSDevMgr": "typedef struct OSDevMgr_s { s32 active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; s32 (*dma)(s32, u32, void *, u32); s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32); } OSDevMgr;",
    "OSPfs": "typedef struct OSPfs_s { struct OSIoMesg_s ioMesgBuf; struct OSMesgQueue_s *queue; s32 channel; u8 activebank; u8 banks; u8 status; union { u8 inodeTable[256]; u8 inode_table[256]; u8 minode_table[256]; }; u8 dir[256]; u8 dir_table[256]; u32 dir_size; u32 inode_start_page; u32 label[8]; s32 repairList[256]; u32 version; u32 checksum; u32 inodeCacheIndex; u8 inodeCache[256]; } OSPfs;",
    "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;",
    "LookAt": "typedef struct { struct { float x, y, z; float pad; } l[2]; } LookAt;",
    "Vtx_t": "typedef struct { s16 ob[3]; u16 flag; s16 tc[2]; u8 cn[4]; } Vtx_t;",
    "Vtx_n": "typedef struct { s16 ob[3]; u16 flag; s16 tc[2]; s8 n[4]; u8 a; } Vtx_n;",
    "Vtx": "typedef union { Vtx_t v; Vtx_n n; long long int force_align[8]; } Vtx;",
    "__OSViCommonRegs": "typedef struct { u32 ctrl; u32 width; u32 burst; u32 vSync; u32 hSync; u32 leap; u32 hStart; u32 xScale; } __OSViCommonRegs;",
    "__OSViFieldRegs": "typedef struct { u32 origin; u32 yScale; u32 vStart; u32 vBurst; u32 vIntr; } __OSViFieldRegs;",
    "OSViMode": "typedef struct OSViMode_s { u32 type; __OSViCommonRegs comRegs; __OSViFieldRegs fldRegs[2]; } OSViMode;",
    "OSViContext": "typedef struct OSViContext_s { u16 state; u16 retraceCount; void *framep; struct OSViMode_s *modep; u32 control; struct OSMesgQueue_s *msgq; OSMesg msg; } OSViContext;",
    "OSTask_t": "typedef struct { u32 type; u32 flags; u64 *ucode_boot; u32 ucode_boot_size; u64 *ucode; u32 ucode_size; u64 *ucode_data; u32 ucode_data_size; u64 *dram_stack; u32 dram_stack_size; u64 *output_buff; u64 *output_buff_size; u64 *data_ptr; u32 data_size; u64 *yield_data_ptr; u32 yield_data_size; } OSTask_t;",
    "OSTask": "typedef union { OSTask_t t; long long int force_align[16]; } OSTask;",
    "Gfx": "typedef struct { u32 words[2]; } Gfx;",
    "Acmd": "typedef union { struct { u32 w0; u32 w1; } words; long long int force_align[1]; } Acmd;",
    "Light_t": "typedef struct { u8 col[3]; u8 pad0; u8 colc[3]; u8 pad1; s8 dir[3]; u8 pad2; } Light_t;",
    "Light": "typedef union { Light_t l; long long int force_align[2]; } Light;",
    "Hilite_t": "typedef struct { int x1, y1, x2, y2; } Hilite_t;",
    "Hilite": "typedef union { Hilite_t h; long long int force_align[2]; } Hilite;",
    "uSprite": "typedef struct { s16 objX, objY; u16 scaleW, scaleH; s16 imageW, imageH; u16 paddedW, paddedH; u16 bitmapW, bitmapH; s16 imageX, imageY; u16 imageFlags; } uSprite;",
    "CPUState": "typedef struct { u32 gpr[32]; u32 sr, pc, cause, badvaddr, sp, ra; u32 lo, hi; u32 fpr[32]; u32 fpcsr; } CPUState;",
    "Struct_core2_7AF80_1": "typedef struct Struct_core2_7AF80_1_s { long long int force_align[64]; } Struct_core2_7AF80_1;",
    "MapModelDescription": "typedef struct MapModelDescription_s { long long int force_align[64]; } MapModelDescription;",
    "MapProgressFlagToDialogID": "typedef struct MapProgressFlagToDialogID_s { long long int force_align[64]; } MapProgressFlagToDialogID;",
}

# Strict bottom-up instantiation order
_STRUCT_ORDER = [
    "Mtx", "OSContStatus", "OSContPad",
    "__OSThreadContext", "OSThread", "OSMesgQueue", "OSMesgHdr",
    "__OSBlockInfo", "__OSTranxInfo", "OSPiHandle", "OSIoMesg", "OSDevMgr", "OSPfs", "OSTimer",
    "LookAt", "Vtx_t", "Vtx_n", "Vtx",
    "__OSViCommonRegs", "__OSViFieldRegs", "OSViMode", "OSViContext",
    "OSTask_t", "OSTask", "Gfx", "Acmd", "Light_t", "Light", "Hilite_t", "Hilite",
    "uSprite", "CPUState", "Struct_core2_7AF80_1", "MapModelDescription", "MapProgressFlagToDialogID"
]

_TYPED_SOURCE_GLOBAL_DECLS = {
    "osTvType":         "extern u32 osTvType;",
    "osRomBase":        "extern u32 osRomBase;",
    "osResetType":      "extern u32 osResetType;",
    "osAppNMIBuffer":   "extern u32 osAppNMIBuffer;",
    "osClockRate":      "extern OSTime osClockRate;",
    "osViModeNtscLan1": "extern OSViMode osViModeNtscLan1;",
    "osViModePalLan1":  "extern OSViMode osViModePalLan1;",
    "osViModeMpalLan1": "extern OSViMode osViModeMpalLan1;",
    "osPiRawStartDma":  "extern s32 osPiRawStartDma(s32, u32, void *, u32);",
    "osEPiRawStartDma": "extern s32 osEPiRawStartDma(struct OSPiHandle_s *, s32, u32, void *, u32);",
    "__OSGlobalIntMask": "extern u32 __OSGlobalIntMask;",
}

N64_OS_OPAQUE_TYPES = {
    "OSPfs", "OSContStatus", "OSContPad", "OSPiHandle", "OSMesgQueue", "OSThread",
    "OSIoMesg", "OSTimer", "OSScTask", "OSTask", "OSScClient", "OSScKiller",
    "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr", "OSPfsState", "OSPfsFile",
    "OSPfsDir", "OSDevMgr", "SPTask", "GBIarg", "OSYieldResult", "OSEvent",
    "Acmd", "Gfx", "Light", "Hilite", "uSprite", "CPUState"
}

# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------
def normalize_path(filepath: str) -> str:
    if ".." in filepath:
        filepath = os.path.normpath(filepath).replace('\\', '/')
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath: return filepath.split(marker)[-1]
    return filepath.lstrip("/") if filepath.startswith("/") else filepath

def clean_nested_linkage_comments(line: str) -> str:
    """Safely strips out old comment structures from a single line to avoid C nesting errors."""
    line = line.replace("/* AUTO-FIX LINKAGE:", "")
    line = line.replace("*/", "")
    line = line.replace("// AUTO-FIX LINKAGE:", "")
    return line.strip()

def _find_synth_internals() -> Optional[str]:
    candidates = [SYNTH_INTERNALS_H, SYNTH_INTERNALS_H_ALT, "include/synthInternals.h"]
    for root, _, files in os.walk("include"):
        for f in files:
            if f == "synthInternals.h":
                candidates.append(os.path.join(root, f))
    for c in candidates:
        if os.path.exists(c): return c
    return None

def patch_synth_internals() -> bool:
    path = _find_synth_internals()
    if not path: return False
    content = read_file(path)
    if "N64_AUDIO_STATES_DEFINED" in content: return False
    write_file(path, _AUDIO_STATE_PREAMBLE + content)
    logger.info(f"Patched audio state typedefs into {path}")
    return True

def patch_exceptasm() -> bool:
    path = "Android/app/src/main/cpp/ultra/exceptasm.cpp"
    if not os.path.exists(path): return False
    content = read_file(path)
    original = content
    content = re.sub(r'\bvolatile\s+(uint32_t|u32)\s+(__OSGlobalIntMask\s*=)', r'\1 \2', content)
    content = re.sub(r'reinterpret_cast<uint32_t\*>\(\s*__osRunningThread->context\s*\)', r'reinterpret_cast<uint32_t*>(&__osRunningThread->context)', content)
    if content != original:
        write_file(path, content)
        logger.info(f"Patched volatile variables in {path}")
        return True
    return False

# ---------------------------------------------------------------------------
# Core Fix Logic
# ---------------------------------------------------------------------------
def apply_fixes(categories: dict) -> Tuple[int, set]:
    fixes       = 0
    fixed_files = set()

    # Expand our hardcoded struct knowledge base if error_parser exists
    for k, v in _EP_STRUCTS.items():
        if k not in _ALL_STRUCTS: _ALL_STRUCTS[k] = v

    # 1. Deterministic n64_types.h Rebuild (Bypasses all stripping bugs)
    types_content = "#pragma once\n\n"
    types_content += _CORE_PRIMITIVES + "\n\n"

    # Strict Dependency-Ordered Body Injection
    for tag in _STRUCT_ORDER:
        if tag in _ALL_STRUCTS:
            types_content += f"#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{_ALL_STRUCTS[tag]}\n#endif\n\n"

    # Inject anything else gathered dynamically that wasn't part of the core ordering
    for tag, body in _ALL_STRUCTS.items():
        if tag not in _STRUCT_ORDER and tag not in {"OSScTask"}:
            types_content += f"#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{body}\n#endif\n\n"

    # Handle opaque placeholders that don't have bodies
    for tag in N64_OS_OPAQUE_TYPES:
        if tag not in _ALL_STRUCTS:
            struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
            types_content += f"#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\nstruct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n#endif\n\n"

    types_content += _AUDIO_STATE_PREAMBLE + "\n\n"

    # Mandatory Global Absolute Bottom Injection
    types_content += "/* Forward declarations for source-defined typed globals */\n"
    types_content += "#ifndef OSViMode_fwd\n#define OSViMode_fwd\ntypedef struct OSViMode_s OSViMode;\n#endif\n"
    types_content += '#ifdef __cplusplus\nextern "C" {\n#endif\n'
    for decl in _TYPED_SOURCE_GLOBAL_DECLS.values():
        types_content += f"{decl}\n"
    types_content += '#ifdef __cplusplus\n}\n#endif\n'

    write_file(TYPES_HEADER, types_content)
    fixes += 1
    fixed_files.add(TYPES_HEADER)
    logger.info(f"Rebuilt {TYPES_HEADER} explicitly to resolve dependency orders.")

    if patch_synth_internals():
        fixes += 1
        fixed_files.add(_find_synth_internals() or "synthInternals.h")

    if patch_exceptasm():
        fixes += 1
        fixed_files.add("Android/app/src/main/cpp/ultra/exceptasm.cpp")

    # 2. Scrape Build Logs to Process Linkage Conflicts
    log_candidates = ["Android/full_build_log.txt", "full_build_log.txt", "build_log.txt"]
    linkage_conflict_files = set()

    for log_file in log_candidates:
        if not os.path.exists(log_file): continue
        content = read_file(log_file)
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            m = re.search(r"error:\s+declaration of '([A-Za-z0-9_]+)' has a different language linkage", line)
            if m:
                func = m.group(1)
                for j in range(i + 1, min(i + 6, len(lines))):
                    m_note = re.search(r"^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+note:\s+previous declaration", lines[j])
                    if m_note:
                        linkage_conflict_files.add((normalize_path(m_note.group(1)), func))
                        break

    # 3. Apply Linkage Conflict Fixes with Safe String Scrubbing
    for filepath, func in linkage_conflict_files:
        if func in _STDLIB_FUNCS and os.path.exists(filepath):
            c = read_file(filepath)
            original_c = c
            
            lines = c.split('\n')
            for i, line in enumerate(lines):
                if func in line and "AUTO-FIX LINKAGE" in line:
                    # Scrub entirely to raw string
                    raw_line = clean_nested_linkage_comments(line)
                    # Safely apply line comment
                    lines[i] = f"// AUTO-FIX LINKAGE: {raw_line}"
                elif func in line and re.match(rf"^[^\n]*\b{re.escape(func)}\s*\(", line.strip()):
                    lines[i] = f"// AUTO-FIX LINKAGE: {line}"

            c = '\n'.join(lines)
            if c != original_c:
                if "#include <math.h>" not in c and func in {"sinf", "cosf", "sqrtf", "sin", "cos", "sqrt", "tan", "tanf", "acosf", "asinf", "atanf", "atan2f"}:
                    c = "#include <math.h>\n" + c
                write_file(filepath, c)
                fixed_files.add(filepath)
                fixes += 1

    return fixes, fixed_files

if __name__ == "__main__":
    apply_fixes({})
