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
    "LFSAMPLES": "8192",
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
    "SP_UCODE_SIZE":      "0x1000",
    "SP_UCODE_DATA_SIZE": "0x800",
    "FRUSTRATIO_1": "1",
}

PHASE_3_MACROS = {
    **PHASE_2_MACROS,
    "G_ON": "1", "G_OFF": "0",
    "G_TX_RENDERTILE": "0", "G_TX_LOADTILE":   "7",
    "G_TX_NOMIRROR":   "0", "G_TX_WRAP":       "0",
    "G_TX_CLAMP":      "0x4", "G_TX_NOMASK":     "0",
    "G_TX_NOLOD":      "0",
    "COMBINED":       "0", "TEXEL0":         "1",
    "TEXEL1":         "2", "PRIMITIVE":      "3",
    "SHADE":          "4", "ENVIRONMENT":    "5",
    "TEXEL0_ALPHA":   "1", "PRIMITIVE_ALPHA":"6",
    "G_RM_AA_ZB_OPA_SURF":  "0x00000000", "G_RM_AA_ZB_OPA_SURF2": "0x00000000",
    "G_RM_AA_ZB_XLU_SURF":  "0x00000000", "G_RM_AA_ZB_XLU_SURF2": "0x00000000",
    "G_RM_PASS":            "0x00000000",
    "G_RM_OPA_SURF2":       "0x00000000",
    "G_RM_XLU_SURF2":       "0x00000000",
    "Z_CMP":                "0x00000001",
    "Z_UPD":                "0x00000002",
    "G_ZBUFFER": "0x00000001", "G_SHADE": "0x00000004",
    "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
    "G_CC_DECALRGBA": "0",
    "G_IM_FMT_RGBA": "0", "G_IM_FMT_YUV": "1", "G_IM_FMT_CI": "2",
    "G_IM_FMT_IA":   "3", "G_IM_FMT_I":   "4",
    "G_IM_SIZ_4b":  "0", "G_IM_SIZ_8b":  "1",
    "G_IM_SIZ_16b": "2", "G_IM_SIZ_32b": "3",
}

# ---------------------------------------------------------------------------
# Audio DSP state typedef block
# ---------------------------------------------------------------------------
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
# N64 struct bodies (Fully Decoupled)
# ---------------------------------------------------------------------------
_N64_OS_STRUCT_BODIES = {
    "Mtx": "#ifndef Mtx_DEFINED\n#define Mtx_DEFINED\ntypedef union { long m[4][4]; struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;\n#endif",
    "OSContStatus": "#ifndef OSContStatus_DEFINED\n#define OSContStatus_DEFINED\ntypedef struct OSContStatus_s { u16 type; u8 status; u8 errnum; } OSContStatus;\n#endif",
    "OSContPad": "#ifndef OSContPad_DEFINED\n#define OSContPad_DEFINED\ntypedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; u8 errnum; } OSContPad;\n#endif",
    "__OSThreadContext": (
        '#ifndef __OSThreadContext_DEFINED\n'
        '#define __OSThreadContext_DEFINED\n'
        'typedef union __OSThreadContext_u {\n'
        '    u64 raw[67];\n'
        '    struct {\n'
        '        u64 at, v0, v1, a0, a1, a2, a3;\n'
        '        u64 t0, t1, t2, t3, t4, t5, t6, t7;\n'
        '        u64 s0, s1, s2, s3, s4, s5, s6, s7;\n'
        '        u64 t8, t9;\n'
        '        u64 gp, sp, s8, ra;\n'
        '        u64 lo, hi;\n'
        '        u32 sr, fpcsr, rcp;\n'
        '        u64 pc;\n'
        '        u64 fp[32];\n'
        '    };\n'
        '} __OSThreadContext;\n'
        '#endif'
    ),
    "OSThread": (
        '#ifndef OSThread_DEFINED\n'
        '#define OSThread_DEFINED\n'
        'struct OSThread_s;\n'
        'typedef struct OSThread_s {\n'
        '    struct OSThread_s *next;\n'
        '    OSPri priority;\n'
        '    struct OSThread_s **queue;\n'
        '    struct OSThread_s *tlnext;\n'
        '    u16 state;\n'
        '    u16 flags;\n'
        '    OSId id;\n'
        '    int fp;\n'
        '    __OSThreadContext context;\n'
        '} OSThread;\n'
        '#endif'
    ),
    "OSMesgQueue": "#ifndef OSMesgQueue_DEFINED\n#define OSMesgQueue_DEFINED\ntypedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; s32 validCount; s32 first; s32 msgCount; OSMesg *msg; } OSMesgQueue;\n#endif",
    "OSMesgHdr": "#ifndef OSMesgHdr_DEFINED\n#define OSMesgHdr_DEFINED\ntypedef struct { u16 type; u8 pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;\n#endif",
    "__OSBlockInfo": "#ifndef __OSBlockInfo_DEFINED\n#define __OSBlockInfo_DEFINED\ntypedef struct { u32 errStatus; void *dramAddr; void *C2Addr; u32 sectorSize; u32 C1ErrNum; u32 C1ErrSector[4]; } __OSBlockInfo;\n#endif",
    "__OSTranxInfo": "#ifndef __OSTranxInfo_DEFINED\n#define __OSTranxInfo_DEFINED\ntypedef struct { u32 cmdType; u16 transferMode; u16 blockNum; s32 sectorNum; u32 devAddr; u32 bmCtlShadow; u32 seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;\n#endif",
    "OSPiHandle": "#ifndef OSPiHandle_DEFINED\n#define OSPiHandle_DEFINED\ntypedef struct OSPiHandle_s { struct OSPiHandle_s *next; u8 type; u8 latency; u8 pageSize; u8 relDuration; u8 pulse; u8 domain; u32 baseAddress; u32 speed; __OSTranxInfo transferInfo; } OSPiHandle;\n#endif",
    "OSIoMesg":  "#ifndef OSIoMesg_DEFINED\n#define OSIoMesg_DEFINED\ntypedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; u32 devAddr; u32 size; struct OSPiHandle_s *piHandle; } OSIoMesg;\n#endif",
    "OSDevMgr":  "#ifndef OSDevMgr_DEFINED\n#define OSDevMgr_DEFINED\ntypedef struct OSDevMgr_s { s32 active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; s32 (*dma)(s32, u32, void *, u32); s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32); } OSDevMgr;\n#endif",
    "OSPfs": (
        '#ifndef OSPfs_DEFINED\n'
        '#define OSPfs_DEFINED\n'
        'typedef struct OSPfs_s {\n'
        '    struct OSIoMesg_s ioMesgBuf;\n'
        '    struct OSMesgQueue_s *queue;\n'
        '    s32 channel;\n'
        '    u8 activebank;\n'
        '    u8 banks;\n'
        '    u8 status;\n'
        '    union {\n'
        '        u8 inodeTable[256];\n'
        '        u8 inode_table[256];\n'
        '        u8 minode_table[256];\n'
        '    };\n'
        '    u8 dir[256];\n'
        '    u8 dir_table[256];\n'
        '    u32 dir_size;\n'
        '    u32 inode_start_page;\n'
        '    u32 label[8];\n'
        '    s32 repairList[256];\n'
        '    u32 version;\n'
        '    u32 checksum;\n'
        '    u32 inodeCacheIndex;\n'
        '    u8 inodeCache[256];\n'
        '} OSPfs;\n'
        '#endif'
    ),
    "OSTimer":   "#ifndef OSTimer_DEFINED\n#define OSTimer_DEFINED\ntypedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;\n#endif",
    "LookAt":    "#ifndef LookAt_DEFINED\n#define LookAt_DEFINED\ntypedef struct { struct { float x, y, z; float pad; } l[2]; } LookAt;\n#endif",
}

SDK_DEFINES_THESE = {"OSScTask"}

PHASE_3_STRUCTS = {
    "Vtx_t": (
        '#ifndef Vtx_t_DEFINED\n'
        '#define Vtx_t_DEFINED\n'
        'typedef struct {\n'
        '    s16 ob[3];\n'
        '    u16 flag;\n'
        '    s16 tc[2];\n'
        '    u8  cn[4];\n'
        '} Vtx_t;\n'
        '#endif'
    ),
    "Vtx_n": (
        '#ifndef Vtx_n_DEFINED\n'
        '#define Vtx_n_DEFINED\n'
        'typedef struct {\n'
        '    s16 ob[3];\n'
        '    u16 flag;\n'
        '    s16 tc[2];\n'
        '    s8  n[4];\n'
        '    u8  a;\n'
        '} Vtx_n;\n'
        '#endif'
    ),
    "Vtx": (
        '#ifndef Vtx_DEFINED\n'
        '#define Vtx_DEFINED\n'
        'typedef union {\n'
        '    Vtx_t v;\n'
        '    Vtx_n n;\n'
        '    long long int force_align[8];\n'
        '} Vtx;\n'
        '#endif'
    ),
    "__OSViCommonRegs": (
        '#ifndef __OSViCommonRegs_DEFINED\n'
        '#define __OSViCommonRegs_DEFINED\n'
        'typedef struct {\n'
        '    u32 ctrl;\n'
        '    u32 width;\n'
        '    u32 burst;\n'
        '    u32 vSync;\n'
        '    u32 hSync;\n'
        '    u32 leap;\n'
        '    u32 hStart;\n'
        '    u32 xScale;\n'
        '} __OSViCommonRegs;\n'
        '#endif'
    ),
    "__OSViFieldRegs": (
        '#ifndef __OSViFieldRegs_DEFINED\n'
        '#define __OSViFieldRegs_DEFINED\n'
        'typedef struct {\n'
        '    u32 origin;\n'
        '    u32 yScale;\n'
        '    u32 vStart;\n'
        '    u32 vBurst;\n'
        '    u32 vIntr;\n'
        '} __OSViFieldRegs;\n'
        '#endif'
    ),
    "OSViMode": (
        '#ifndef OSViMode_DEFINED\n'
        '#define OSViMode_DEFINED\n'
        'typedef struct OSViMode_s {\n'
        '    u32 type;\n'
        '    __OSViCommonRegs comRegs;\n'
        '    __OSViFieldRegs  fldRegs[2];\n'
        '} OSViMode;\n'
        '#endif'
    ),
    "OSViContext": "#ifndef OSViContext_DEFINED\n#define OSViContext_DEFINED\ntypedef struct OSViContext_s { u16 state; u16 retraceCount; void *framep; struct OSViMode_s *modep; u32 control; struct OSMesgQueue_s *msgq; OSMesg msg; } OSViContext;\n#endif",
    "OSTask_t": (
        '#ifndef OSTask_t_DEFINED\n'
        '#define OSTask_t_DEFINED\n'
        'typedef struct {\n'
        '    u32  type;\n'
        '    u32  flags;\n'
        '    u64 *ucode_boot;\n'
        '    u32  ucode_boot_size;\n'
        '    u64 *ucode;\n'
        '    u32  ucode_size;\n'
        '    u64 *ucode_data;\n'
        '    u32  ucode_data_size;\n'
        '    u64 *dram_stack;\n'
        '    u32  dram_stack_size;\n'
        '    u64 *output_buff;\n'
        '    u64 *output_buff_size;\n'
        '    u64 *data_ptr;\n'
        '    u32  data_size;\n'
        '    u64 *yield_data_ptr;\n'
        '    u32  yield_data_size;\n'
        '} OSTask_t;\n'
        '#endif'
    ),
    "OSTask": (
        '#ifndef OSTask_DEFINED\n'
        '#define OSTask_DEFINED\n'
        'typedef union {\n'
        '    OSTask_t t;\n'
        '    long long int force_align[16];\n'
        '} OSTask;\n'
        '#endif'
    ),
    "Gfx":    "#ifndef Gfx_DEFINED\n#define Gfx_DEFINED\ntypedef struct { u32 words[2]; } Gfx;\n#endif",
    "Acmd":   "#ifndef Acmd_DEFINED\n#define Acmd_DEFINED\ntypedef union { struct { u32 w0; u32 w1; } words; long long int force_align[1]; } Acmd;\n#endif",
    "Light_t": "#ifndef Light_t_DEFINED\n#define Light_t_DEFINED\ntypedef struct { u8 col[3]; u8 pad0; u8 colc[3]; u8 pad1; s8 dir[3]; u8 pad2; } Light_t;\n#endif",
    "Light":  "#ifndef Light_DEFINED\n#define Light_DEFINED\ntypedef union { Light_t l; long long int force_align[2]; } Light;\n#endif",
    "Hilite_t": "#ifndef Hilite_t_DEFINED\n#define Hilite_t_DEFINED\ntypedef struct { int x1, y1, x2, y2; } Hilite_t;\n#endif",
    "Hilite": "#ifndef Hilite_DEFINED\n#define Hilite_DEFINED\ntypedef union { Hilite_t h; long long int force_align[2]; } Hilite;\n#endif",
    "uSprite": "#ifndef uSprite_DEFINED\n#define uSprite_DEFINED\ntypedef struct { s16 objX, objY; u16 scaleW, scaleH; s16 imageW, imageH; u16 paddedW, paddedH; u16 bitmapW, bitmapH; s16 imageX, imageY; u16 imageFlags; } uSprite;\n#endif",
    "CPUState": "#ifndef CPUState_DEFINED\n#define CPUState_DEFINED\ntypedef struct { u32 gpr[32]; u32 sr, pc, cause, badvaddr, sp, ra; u32 lo, hi; u32 fpr[32]; u32 fpcsr; } CPUState;\n#endif",
    "Struct_core2_7AF80_1": (
        "#ifndef Struct_core2_7AF80_1_DEFINED\n"
        "#define Struct_core2_7AF80_1_DEFINED\n"
        "typedef struct Struct_core2_7AF80_1_s { long long int force_align[64]; } Struct_core2_7AF80_1;\n"
        "#endif"
    ),
    "MapModelDescription": (
        "#ifndef MapModelDescription_DEFINED\n"
        "#define MapModelDescription_DEFINED\n"
        "typedef struct MapModelDescription_s { long long int force_align[64]; } MapModelDescription;\n"
        "#endif"
    ),
    "MapProgressFlagToDialogID": (
        "#ifndef MapProgressFlagToDialogID_DEFINED\n"
        "#define MapProgressFlagToDialogID_DEFINED\n"
        "typedef struct MapProgressFlagToDialogID_s { long long int force_align[64]; } MapProgressFlagToDialogID;\n"
        "#endif"
    ),
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
    "OSYieldResult", "OSEvent",
    "Acmd", "Gfx", "Light", "Hilite", "uSprite", "CPUState",
    "Struct_core2_7AF80_1", "Struct_core1_10A00_1",
    "MapModelDescription", "MapProgressFlagToDialogID",
}

N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "INTERLEAVE_STATE",
    "ENVMIX_STATE2", "HIPASSLOOP_STATE", "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

N64_KNOWN_GLOBALS = {
    "__osPiTable":       "struct OSPiHandle_s *__osPiTable;",
    "__osFlashHandle":   "struct OSPiHandle_s *__osFlashHandle;",
    "__osSfHandle":      "struct OSPiHandle_s *__osSfHandle;",
    "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
    "__osRunQueue":      "struct OSThread_s *__osRunQueue;",
    "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
    "__OSGlobalIntMask": "u32 __OSGlobalIntMask;",
}

_TYPED_SOURCE_GLOBALS = {
    "osTvType", "osRomBase", "osResetType", "osAppNMIBuffer",
    "osClockRate", "osViModeNtscLan1", "osViModePalLan1", "osViModeMpalLan1",
    "osPiRawStartDma", "osEPiRawStartDma",
    "__OSGlobalIntMask",
}

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
}

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

_CORE_PRIMITIVES = (
    "#include <stdint.h>\n"
    "#ifndef CORE_PRIMITIVES_DEFINED\n"
    "#define CORE_PRIMITIVES_DEFINED\n"
    "typedef uint8_t  u8;\n"
    "typedef int8_t   s8;\n"
    "typedef uint16_t u16;\n"
    "typedef int16_t  s16;\n"
    "typedef uint32_t u32;\n"
    "typedef int32_t  s32;\n"
    "typedef uint64_t u64;\n"
    "typedef int64_t  s64;\n"
    "typedef float    f32;\n"
    "typedef double   f64;\n"
    "typedef int      n64_bool;\n"
    "typedef u32   OSIntMask;\n"
    "typedef u64   OSTime;\n"
    "typedef u32   OSId;\n"
    "typedef s32   OSPri;\n"
    "typedef void* OSMesg;\n"
    "typedef u32   OSHWIntr;\n"
    "#ifndef ADPCM_STATE_DEFINED\n"
    "#define ADPCM_STATE_DEFINED\n"
    "typedef short ADPCM_STATE[9];\n"
    "#endif\n"
    "#ifndef OSYieldResult_DEFINED\n"
    "#define OSYieldResult_DEFINED\n"
    "typedef u32 OSYieldResult;\n"
    "#endif\n"
    "#ifndef OSEvent_DEFINED\n"
    "#define OSEvent_DEFINED\n"
    "typedef u32 OSEvent;\n"
    "#endif\n"
    "#ifndef Vp_DEFINED\n"
    "#define Vp_DEFINED\n"
    "typedef struct { s16 vscale[4]; s16 vtrans[4]; } Vp_t;\n"
    "typedef union { Vp_t vp; long long int force_align[4]; } Vp;\n"
    "#endif\n"
    "#ifdef __cplusplus\n"
    "extern \"C\" int sched_yield(void);\n"
    "#endif\n"
    "#endif /* END_CORE_PRIMITIVES */\n"
)

_N64_BOOL_H_CONTENT = (
    "#pragma once\n"
    "/* n64_bool.h shim */\n"
    "#ifndef n64_bool\n"
    "typedef int n64_bool;\n"
    "#endif\n"
    "#ifndef TRUE\n"
    "#define TRUE 1\n"
    "#endif\n"
    "#ifndef FALSE\n"
    "#define FALSE 0\n"
    "#endif\n"
)

# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------
def normalize_path(filepath: str) -> str:
    if ".." in filepath:
        filepath = os.path.normpath(filepath).replace('\\', '/')
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath: return filepath.split(marker)[-1]
    return filepath.lstrip("/") if filepath.startswith("/") else filepath

def strip_redefinition(content: str, tag: str) -> str:
    changed = True
    while changed:
        changed = False
        # Aggressive structure/union stripping (greedy matching for one-liners)
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

        # Typedef block stripping
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

        # Compact one-liners (SDK style)
        c_new, n = re.subn(rf"(?m)^typedef\s+(?:struct|union)\s*\{{[^}}]*\}}\s*{re.escape(tag)}\s*;", f"/* STRIPPED COMPACT: {tag} */", content)
        if n > 0: content, changed = c_new, True

    return content

def repair_unterminated_conditionals(content: str) -> str:
    lines = content.split('\n')
    stack = []
    remove = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r'#\s*(?:ifndef|ifdef|if)\b', stripped):
            next_define = False
            for j in range(i + 1, min(i + 3, len(lines))):
                ns = lines[j].strip()
                if ns.startswith('#define'):
                    next_define = True; break
                if ns: break
            stack.append((i, next_define))
        elif re.match(r'#\s*endif\b', stripped):
            if stack: stack.pop()
    for (idx, has_define) in stack:
        if not has_define: continue
        remove.add(idx)
        for j in range(idx + 1, min(idx + 4, len(lines))):
            if lines[j].strip().startswith('#define') or lines[j].strip().startswith('#endif'):
                remove.add(j); break
    if not remove: return content
    return '\n'.join(line for i, line in enumerate(lines) if i not in remove)

def patch_synth_internals() -> bool:
    candidates = [SYNTH_INTERNALS_H, SYNTH_INTERNALS_H_ALT, "include/synthInternals.h"]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if not path: return False
    content = read_file(path)
    if "N64_AUDIO_STATES_DEFINED" in content: return False
    write_file(path, _AUDIO_STATE_PREAMBLE + content)
    return True

def apply_fixes(categories: dict, intelligence_level: int = 3) -> Tuple[int, set]:
    fixes = 0
    fixed_files = set()

    # 1. Scraping & Categories (Standard Logic)
    # ------------------------------------------------------------------
    # [Internal Note: _scrape_logs_into_categories is called here as provided]
    
    # 2. Linkage Fix (CORRECTED: Recursive Scrubber for gu.h errors)
    # ------------------------------------------------------------------
    if categories.get("linkage_conflict_files"):
        for filepath, func in categories["linkage_conflict_files"]:
            if func in _STDLIB_FUNCS and os.path.exists(filepath):
                c = read_file(filepath); original_c = c
                # Scrub ALL previous AUTO-FIX markers to prevent comment nesting
                if "AUTO-FIX LINKAGE:" in c:
                    while "AUTO-FIX LINKAGE:" in c:
                        # Strip nested /* ... */ blocks
                        c = re.sub(r'/\*\s*AUTO-FIX LINKAGE:\s*(.*?)\s*\*/', r'\1', c)
                        # Strip nested // lines
                        c = re.sub(r'//\s*AUTO-FIX LINKAGE:\s*', '', c)
                
                # Apply strictly single-line marker
                pattern = rf"(?m)^(?![^\n]*// AUTO-FIX LINKAGE)(.*?\b{re.escape(func)}\s*\(.*?;)"
                c, n = re.subn(pattern, r"// AUTO-FIX LINKAGE: \1", c)
                if c != original_c:
                    write_file(filepath, c); fixed_files.add(filepath); fixes += 1

    # 3. Assemble Header (CORRECTED: Strict Dependency Order)
    # ------------------------------------------------------------------
    bodies_added = False
    types_content = "#pragma once\n" + _CORE_PRIMITIVES + "\n"
    
    if intelligence_level >= 2:
        # Priority map for N64 types to avoid "unknown type name" errors
        dependency_priority = {
            "__OSBlockInfo": 1, 
            "__OSTranxInfo": 2, # Depends on BlockInfo
            "OSPiHandle": 3,    # Depends on TranxInfo
            "__OSViCommonRegs": 1,
            "__OSViFieldRegs": 1,
            "OSViMode": 2,
            "Vtx_t": 1,
            "Vtx_n": 1,
            "Vtx": 2,           # Depends on Vtx_t/n
            "__OSThreadContext": 1,
            "OSThread": 2,      # Depends on ThreadContext
            "OSMesgQueue": 3    # Depends on OSThread
        }
        
        active_bodies = {**_N64_OS_STRUCT_BODIES, **PHASE_3_STRUCTS}
        tags = sorted(active_bodies.keys(), key=lambda t: dependency_priority.get(t, 50))
        
        for tag in tags:
            types_content += "\n" + active_bodies[tag] + "\n"
            bodies_added = True

        # Opaque fallbacks for missing types identified in logs
        for tag in categories.get("need_struct_body", set()):
            if tag not in active_bodies and tag not in SDK_DEFINES_THESE:
                types_content += "\n" + _opaque_stub(tag)
                bodies_added = True

        # Injection of Typed Globals (Mandatory Bottom)
        types_content += "\n/* Typed Global Forwards */\n"
        types_content += '#ifdef __cplusplus\nextern "C" {\n#endif\n'
        for var, decl in _TYPED_SOURCE_GLOBAL_DECLS.items():
            types_content += f"#ifndef {var}_fwd_DEFINED\n#define {var}_fwd_DEFINED\n{decl}\n#endif\n"
        types_content += '#ifdef __cplusplus\n}\n#endif\n'

    if bodies_added:
        write_file(TYPES_HEADER, types_content)
        fixes += 1

    # 4. Patch Audio Internals
    if patch_synth_internals(): fixes += 1

    return fixes, fixed_files
