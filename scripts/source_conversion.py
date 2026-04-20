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

def strip_auto_preamble(content: str) -> str:
    lines = content.split('\n')
    result = []
    in_auto_block = False
    for line in lines:
        s = line.strip()
        if s.startswith("/* AUTO: forward decl"):
            in_auto_block = True; continue
        if in_auto_block and re.match(r'(?:typedef\s+)?(?:struct|union)\s+\w+(?:_s)?\s+\w+\s*;', s):
            continue
        in_auto_block = False
        result.append(line)
    return '\n'.join(result)

def _rename_posix_static(content: str, func_name: str, filepath: str) -> Tuple[str, bool]:
    prefix   = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define   = f"\n// AUTO: rename POSIX-reserved static '{func_name}'\n#define {func_name} {new_name}\n"
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

        # Loose typedef and forward declaration stripping
        c_new, n = re.subn(rf"\btypedef\s+(?:struct\s+|union\s+)?[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;", f"/* STRIPPED LOOSE TYPEDEF: {tag} */", content)
        if n > 0: content, changed = c_new, True
        c_new, n = re.subn(rf"\b(?:struct|union)\s+{re.escape(tag)}\s*;", f"/* STRIPPED FWD DECL: {tag} */", content)
        if n > 0: content, changed = c_new, True
        
        # AGGRESSIVE: Strip compact SDK-style one-liners that bypass \s+ logic
        c_new, n = re.subn(rf"(?m)^typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(tag)}\s*;", f"/* STRIPPED COMPACT: {tag} */", content)
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

def clean_conflicting_typedefs():
    if not os.path.exists(TYPES_HEADER): return
    content = original = read_file(TYPES_HEADER)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg", "OSHWIntr"]:
        content = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s+{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
    if content != original: write_file(TYPES_HEADER, content)

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
    if not path:
        logger.warning("synthInternals.h not found — audio state types cannot be injected at source")
        return False
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
        logger.info(f"Patched volatile __OSGlobalIntMask in {path}")
        return True
    return False

def patch_dialog_missing_include() -> bool:
    path = "src/core2/gc/dialog.c"
    if not os.path.exists(path): return False
    content = read_file(path)
    if 'n64_types.h"' in content or '<n64_types.h>' in content: return False
    write_file(path, '#include "ultra/n64_types.h"\n' + content)
    logger.info(f"Injected n64_types.h include into {path}")
    return True

def ensure_types_header_base(categories: Optional[dict] = None) -> str:
    if categories is None: categories = {}
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "CORE_PRIMITIVES_DEFINED" in content and "/* END_CORE_PRIMITIVES */" not in content: content = ""
        elif categories and categories.get("endif_without_if") and any("n64_types.h" in f for f in categories["endif_without_if"]): content = ""
        if content:
            content = content.replace('#include "ultra/n64_types.h"\n', '')
            if "#pragma once" not in content: content = "#pragma once\n" + content
    else: content = ""

    if not content:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?/\* END_CORE_PRIMITIVES \*/\n?", "", content)
    for p in ["u8","s8","u16","s16","u32","s32","u64","s64","f32","f64","n64_bool", "OSIntMask","OSTime","OSId","OSPri","OSMesg","OSHWIntr"]:
        content = re.sub(rf"\btypedef\s+[^;]+\b{re.escape(p)}\s*;", "", content)
    for p in ["OSIntMask","OSTime","OSId","OSPri","OSMesg","OSHWIntr"]:
        content = re.sub(rf"(?:typedef\s+)?(?:struct\s+|union\s+)?{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(p)}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+(?:struct|union)\s+{re.escape(p)}(?:_s)?\s+{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"(?:struct|union)\s+{re.escape(p)}(?:_s)?\s*;\n?", "", content)

    content = content.replace("#pragma once", f"#pragma once\n{_CORE_PRIMITIVES}", 1)
    content = repair_unterminated_conditionals(content)
    write_file(TYPES_HEADER, content)
    _emit_n64_bool_h()
    return content

def _emit_n64_bool_h():
    shim_locations = [os.path.join(os.path.dirname(TYPES_HEADER), "n64_bool.h")]
    for candidate in ["include/core2/n64_bool.h", "Android/app/src/main/cpp/../../../../../include/core2/n64_bool.h"]:
        if os.path.isdir(os.path.dirname(candidate)): shim_locations.append(candidate)
    for path in shim_locations:
        if not os.path.exists(path):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                write_file(path, _N64_BOOL_H_CONTENT)
            except Exception: pass

def _scrape_logs_into_categories(categories: dict) -> None:
    log_candidates = ["Android/failed_files.log", "Android/full_build_log.txt", "full_build_log.txt", "build_log.txt", "Android/build_log.txt"]
    for f in os.listdir("."):
        if f.endswith((".txt", ".log")): log_candidates.append(f)

    for key in ["missing_types","posix_reserved_conflict","struct_redef","typedef_redef"]:
        categories.setdefault(key, [])
        if isinstance(categories[key], set): categories[key] = list(categories[key])

    for key in ["undeclared_identifiers","implicit_func_stubs","need_struct_body","not_a_pointer","errno_conflict","endif_without_if", "linkage_conflict_funcs", "linkage_conflict_files"]:
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
    endifs = categories["endif_without_if"]

    for log_file in set(log_candidates):
        if not os.path.exists(log_file): continue
        content = read_file(log_file)

        lines = content.split('\n')
        for i, line in enumerate(lines):
            m = re.search(r"error:\s+declaration of '([A-Za-z0-9_]+)' has a different language linkage", line)
            if m:
                func = m.group(1)
                categories.setdefault("linkage_conflict_funcs", set()).add(func)
                for j in range(i + 1, min(i + 6, len(lines))):
                    m_note = re.search(r"^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+note:\s+previous declaration", lines[j])
                    if m_note:
                        categories.setdefault("linkage_conflict_files", set()).add((normalize_path(m_note.group(1)), func))
                        break

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+initializing 'f32'.*?incompatible type 'void \*'", content):
            categories.setdefault("f32_null_init", set()).add(normalize_path(m.group(1)))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+#endif without #if", content):
            endifs.add(normalize_path(m.group(1)))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:.*errno", content):
            err.add(normalize_path(m.group(1)))

        if "errno -> ->errnum" in content or "error: member access into incomplete type" in content and "errno" in content:
            for base_dir in ["src", "Android/app/src/main/cpp", "."]:
                if not os.path.exists(base_dir): continue
                for root, _, files in walk_dir(base_dir):
                    for f in files:
                        if f.endswith(('.c', '.cpp', '.h')): err.add(normalize_path(os.path.join(root, f)))

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

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+typedef redefinition with different types \('struct ([^']+)' vs 'struct ([^']+)'\)", content):
            filepath = normalize_path(m.group(1))
            tag1, tag2 = m.group(2), m.group(3)
            if tag1 == tag2:
                entry = (filepath, tag1)
                if entry not in sr: sr.append(entry)
            elif "unnamed struct" in tag1 or "unnamed struct" in tag2:
                canonical = tag2 if tag2.endswith("_s") else tag1
                entry = (filepath, canonical)
                if entry not in sr: sr.append(entry)
            else:
                entry = (filepath, f"struct {tag1}", f"struct {tag2}")
                categories.setdefault("typedef_redef", [])
                if entry not in categories["typedef_redef"]: categories["typedef_redef"].append(entry)

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+definition of type '([A-Za-z0-9_]+)' conflicts with typedef", content):
            filepath = normalize_path(m.group(1))
            tag = m.group(2)
            entry = (filepath, tag)
            if entry not in sr: sr.append(entry)

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

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+redefinition of '([A-Za-z0-9_]+)' with a different type", content):
            filepath, var = normalize_path(m.group(1)), m.group(2)
            if var in _TYPED_SOURCE_GLOBALS:
                categories.setdefault("type_mismatch_globals", [])
                if (filepath, var) not in categories["type_mismatch_globals"]: categories["type_mismatch_globals"].append((filepath, var))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+redefinition of '([A-Za-z0-9_]+)' as different kind of symbol", content):
            filepath, var = normalize_path(m.group(1)), m.group(2)
            if var in _TYPED_SOURCE_GLOBALS:
                categories.setdefault("type_mismatch_globals", [])
                if (filepath, var) not in categories["type_mismatch_globals"]: categories["type_mismatch_globals"].append((filepath, var))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_]+\.(c|cpp|h)):\d+:\d+:\s+error:\s+no member named '([A-Za-z0-9_]+)' in 'struct ([A-Za-z0-9_]+)'", content):
            filepath = normalize_path(m.group(1))
            member, struct_name = m.group(3), m.group(4)
            base = struct_name[:-2] if struct_name.endswith("_s") else struct_name
            categories.setdefault("missing_members", [])
            entry = (base, member)
            if entry not in categories["missing_members"]: categories["missing_members"].append(entry)

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+no member named '([A-Za-z0-9_]+)' in '(?:union )?([A-Za-z0-9_]+)'", content):
            member, type_name = m.group(2), m.group(3)
            if type_name in ("Vtx_n", "Vtx_t", "Vtx"): nsb.add("Vtx")
            elif type_name == "Vp": nsb.add("Vp")
            elif type_name in ("__OSViCommonRegs", "__OSViFieldRegs"): nsb.add("OSViMode")
            elif "__OSThreadContext" in type_name: nsb.add("OSThread")
            else:
                categories.setdefault("missing_members", [])
                entry = (type_name, member)
                if entry not in categories["missing_members"]: categories["missing_members"].append(entry)

        for m in re.finditer(r"error:\s+no member named '(\w+)' in 'Vtx'", content): nsb.add("Vtx")
        for m in re.finditer(r"error:\s+redefinition of '__OSGlobalIntMask'", content):
            categories.setdefault("type_mismatch_globals", [])
            entry = ("Android/app/src/main/cpp/ultra/exceptasm.cpp", "__OSGlobalIntMask")
            if entry not in categories["type_mismatch_globals"]: categories["type_mismatch_globals"].append(entry)
        for m in re.finditer(r"error:\s+use of undeclared identifier '((?:RESAMPLE|POLEF|ENVMIX|INTERLEAVE|HIPASSLOOP|COMPRESS|REVERB|MIXER)_STATE\w*)'", content): nsb.add(m.group(1))
        for m in re.finditer(r"error:\s+unknown type name '((?:RESAMPLE|POLEF|ENVMIX|INTERLEAVE|HIPASSLOOP|COMPRESS|REVERB|MIXER)_STATE\w*)'", content): nsb.add(m.group(1))
        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+initializer element is not a compile-time constant", content):
            categories.setdefault("gbi_static_init_files", set()).add(normalize_path(m.group(1)))

    deps = {
        "OSPiHandle": ["__OSTranxInfo", "__OSBlockInfo"],
        "__OSTranxInfo": ["__OSBlockInfo"],
        "OSViMode": ["__OSViCommonRegs", "__OSViFieldRegs"],
        "OSViContext": ["OSViMode", "__OSViCommonRegs", "__OSViFieldRegs", "OSMesgQueue", "OSThread", "OSMesgHdr"],
        "OSThread": ["__OSThreadContext"],
        "OSMesgQueue": ["OSThread"],
        "OSPfs": ["OSIoMesg", "OSMesgQueue", "OSPiHandle"],
        "OSIoMesg": ["OSMesgHdr", "OSPiHandle"],
        "OSDevMgr": ["OSThread", "OSMesgQueue", "OSPiHandle"],
        "Vtx": ["Vtx_t", "Vtx_n"]
    }

    added_transitive = True
    while added_transitive:
        added_transitive = False
        current_tags = list(categories.get("need_struct_body", set()))
        for tag in current_tags:
            if tag in deps:
                for d in deps[tag]:
                    if d not in categories["need_struct_body"]:
                        categories["need_struct_body"].add(d)
                        added_transitive = True

def walk_dir(base_dir: str):
    return os.walk(base_dir)

def apply_fixes(categories: dict, intelligence_level: int = 3) -> Tuple[int, set]:
    fixes       = 0
    fixed_files = set()

    if intelligence_level >= 3:
        ACTIVE_MACROS   = PHASE_3_MACROS.copy()
        ACTIVE_STRUCTS  = {k:v for k,v in {**_N64_OS_STRUCT_BODIES, **PHASE_3_STRUCTS}.items() if k not in SDK_DEFINES_THESE}
    elif intelligence_level == 2:
        ACTIVE_MACROS   = PHASE_2_MACROS.copy()
        ACTIVE_STRUCTS  = {k:v for k,v in _N64_OS_STRUCT_BODIES.items() if k not in SDK_DEFINES_THESE}
    else:
        ACTIVE_MACROS   = PHASE_1_MACROS.copy()
        ACTIVE_STRUCTS  = {}

    for k, v in _EP_STRUCTS.items():
        if k not in SDK_DEFINES_THESE and k not in ACTIVE_STRUCTS:
            ACTIVE_STRUCTS[k] = v

    for k, v in _EP_MACROS.items():
        if k not in ACTIVE_MACROS:
            ACTIVE_MACROS[k] = v

    N64_OS_OPAQUE_TYPES.update(_EP_OPAQUE)

    if intelligence_level >= 2:
        for tag in ACTIVE_STRUCTS.keys(): categories.setdefault("need_struct_body", set()).add(tag)
        categories.setdefault("need_struct_body", set()).add("OSTask")

    _scrape_logs_into_categories(categories)
    clean_conflicting_typedefs()
    types_content = ensure_types_header_base(categories)

    if patch_synth_internals():
        fixed_files.add(_find_synth_internals() or "synthInternals.h")
        fixes += 1

    types_content = read_file(TYPES_HEADER)
    if "N64_AUDIO_STATES_DEFINED" not in types_content:
        insert_after = "/* END_CORE_PRIMITIVES */"
        if insert_after in types_content:
            types_content = types_content.replace(insert_after, insert_after + "\n" + _AUDIO_STATE_PREAMBLE, 1)
        else:
            types_content += "\n" + _AUDIO_STATE_PREAMBLE
        write_file(TYPES_HEADER, types_content); fixes += 1

    if patch_exceptasm(): fixed_files.add("Android/app/src/main/cpp/ultra/exceptasm.cpp"); fixes += 1
    if patch_dialog_missing_include(): fixed_files.add("src/core2/gc/dialog.c"); fixes += 1

    if categories.get("f32_null_init"):
        for filepath in categories["f32_null_init"]:
            if os.path.exists(filepath):
                c = read_file(filepath)
                c_new = re.sub(r'\{NULL,\s*NULL\}', '{0.0f, 0.0f}', c)
                c_new = re.sub(r'=\s*NULL;', '= 0.0f;', c_new)
                if c_new != c: write_file(filepath, c_new); fixed_files.add(filepath); fixes += 1

    exceptasm_path = "Android/app/src/main/cpp/ultra/exceptasm.cpp"
    if os.path.exists(exceptasm_path):
        e_content = read_file(exceptasm_path)
        new_e = re.sub(r'reinterpret_cast<uint32_t\*>\(\s*__osRunningThread->context\s*\)', r'reinterpret_cast<uint32_t*>(&__osRunningThread->context)', e_content)
        if new_e != e_content: write_file(exceptasm_path, new_e); fixed_files.add(exceptasm_path); fixes += 1

    if categories.get("errno_conflict"):
        for filepath in list(categories["errno_conflict"]):
            if os.path.exists(filepath):
                c = read_file(filepath)
                new_c = re.sub(r'->errno\b', '->errnum', c)
                new_c = re.sub(r'\.errno\b', '.errnum', new_c)
                if c != new_c: write_file(filepath, new_c); fixed_files.add(filepath); fixes += 1

    if categories.get("linkage_conflict_funcs"):
        types_content = read_file(TYPES_HEADER); changed = False
        for func in categories["linkage_conflict_funcs"]:
            if func in _STDLIB_FUNCS:
                types_content, n = re.subn(rf"(?m)^#ifndef {re.escape(func)}_DEFINED\n.*?#define {re.escape(func)}_DEFINED\nextern[^\n]+{re.escape(func)}[^\n]*\n#endif\n?", "", types_content, flags=re.DOTALL)
                types_content, n2 = re.subn(rf"(?m)^extern\s+long\s+long\s+int\s+{re.escape(func)}\s*\(\s*\)\s*;\n?", "", types_content)
                if n + n2 > 0: changed = True
        if changed: write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("linkage_conflict_files"):
        for filepath, func in categories["linkage_conflict_files"]:
            if func in _STDLIB_FUNCS and os.path.exists(filepath):
                c = read_file(filepath); original_c = c
                # RECURSIVE CLEANUP: Strips previous /* marker */ and // marker patterns to handle gu.h nested errors
                if "AUTO-FIX LINKAGE:" in c:
                    while "AUTO-FIX LINKAGE:" in c:
                        # Strip nested /* AUTO-FIX LINKAGE: ... */ blocks
                        c = re.sub(r'/\*\s*AUTO-FIX LINKAGE:\s*(.*?)\s*\*/', r'\1', c)
                        # Strip nested // AUTO-FIX LINKAGE: ... lines
                        c = re.sub(r'//\s*AUTO-FIX LINKAGE:\s*', '', c)
                    c = c.strip()
                
                # Apply single-line linkage marker strictly using // to avoid comment closure errors
                pattern = rf"(?m)^(?![^\n]*// AUTO-FIX LINKAGE)(.*?\b{re.escape(func)}\s*\(.*?;)"
                c, n = re.subn(pattern, r"// AUTO-FIX LINKAGE: \1", c)
                if c != original_c:
                    if "#include <math.h>" not in c and func in {"sinf", "cosf", "sqrtf", "sin", "cos", "sqrt", "tan", "tanf", "acosf", "asinf", "atanf", "atan2f"}:
                        c = "#include <math.h>\n" + c
                    write_file(filepath, c); fixed_files.add(filepath); fixes += 1

    # ------------------------------------------------------------------
    # PHASE 1: STRUCTS (Aggressive stripping and ordered injection)
    # ------------------------------------------------------------------
    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER); bodies_added = False
        types_content = re.sub(r"(?s)typedef\s+struct\s*\{[^}]*\}\s*Vtx_t;\s*typedef\s+union\s*\{[^}]*\}\s*Vtx;", "", types_content)

        dependency_priority = {
            "__OSBlockInfo": 1, "__OSTranxInfo": 2, "OSPiHandle": 3,
            "__OSViCommonRegs": 1, "__OSViFieldRegs": 2, "OSViMode": 3,
            "Vtx_t": 1, "Vtx_n": 2, "Vtx": 3,
            "__OSThreadContext": 1, "OSThread": 2, "OSMesgQueue": 3,
            "Light_t": 1, "Light": 2, "Hilite_t": 1, "Hilite": 2,
            "OSTask_t": 1, "OSTask": 2
        }
        def struct_sort_key(t):
            if t in dependency_priority: return dependency_priority[t]
            if t in ("OSPiHandle", "OSViMode", "Vtx", "OSThread", "LookAt", "OSTask"): return 100
            return 50

        ordered_tags = sorted([t for t in ACTIVE_STRUCTS.keys() if t in categories.get("need_struct_body", set()) and t not in SDK_DEFINES_THESE], key=struct_sort_key)
        other_tags   = sorted([t for t in categories.get("need_struct_body", set()) if t not in ACTIVE_STRUCTS and t not in SDK_DEFINES_THESE])

        for tag in ordered_tags + other_tags:
            if not isinstance(tag, str): continue
            body = ACTIVE_STRUCTS.get(tag)
            if not body:
                if tag in N64_AUDIO_STATE_TYPES:
                    if not _type_already_defined(tag, types_content):
                        types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};\n#endif\n"; bodies_added = True
                    continue
                if tag in N64_OS_OPAQUE_TYPES and not _type_already_defined(tag, types_content):
                    types_content += "\n" + _opaque_stub(tag); bodies_added = True
                continue

            # Clears all previous versions (compact, block, or union-alias) before re-injecting in order
            types_content = strip_redefinition(types_content, tag)
            if not tag.endswith("_s"): types_content = strip_redefinition(types_content, f"{tag}_s")
            types_content = re.sub(rf"#ifndef {re.escape(tag)}_DEFINED[\s\S]*?#endif\n?", "", types_content)

            types_content += "\n" + body + "\n"; bodies_added = True

        if bodies_added:
            types_content = repair_unterminated_conditionals(types_content)
            write_file(TYPES_HEADER, types_content); fixes += 1

    # ------------------------------------------------------------------
    # PHASE 2: TYPED GLOBALS (Mandatory absolute bottom of header)
    # ------------------------------------------------------------------
    if intelligence_level >= 2:
        types_content = read_file(TYPES_HEADER); original_types = types_content
        scrub_targets = (set(ACTIVE_STRUCTS.keys()) | N64_OS_OPAQUE_TYPES | set(ACTIVE_MACROS.keys()) |
                         {"__osPiTable","__osFlashHandle","__osSfHandle","__osCurrentThread","__osRunQueue","__osFaultedThread"} |
                         _TYPED_SOURCE_GLOBALS)
        
        for target in scrub_targets:
            types_content = re.sub(rf"(?m)^#ifndef {re.escape(target)}_DEFINED\n#define {re.escape(target)}_DEFINED\nextern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?;\n#endif\n?", "", types_content)
            types_content = re.sub(rf"(?m)^extern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?;\n?", "", types_content)
        
        marker = "/* Forward declarations for source-defined typed globals */"
        if marker in types_content: types_content = types_content[:types_content.find(marker)].rstrip() + "\n"

        typed_block = f"\n{marker}\n"
        typed_block += "#ifndef OSViMode_fwd\n#define OSViMode_fwd\ntypedef struct OSViMode_s OSViMode;\n#endif\n"
        typed_block += '#ifdef __cplusplus\nextern "C" {\n#endif\n'
        for var, decl in _TYPED_SOURCE_GLOBAL_DECLS.items(): typed_block += f"#ifndef {var}_fwd_DEFINED\n#define {var}_fwd_DEFINED\n{decl}\n#endif\n"
        typed_block += '#ifdef __cplusplus\n}\n#endif\n'

        types_content += typed_block
        if types_content != original_types: write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("missing_members"):
        types_content = read_file(TYPES_HEADER)
        for item in sorted(categories["missing_members"]):
            struct_name, member_name = item[0], item[1]
            pattern = rf"(struct\s+{re.escape(struct_name)}\s*\{{)([^}}]*?)(\}})"
            if re.search(pattern, types_content):
                def inject_member(match, mn=member_name):
                    body = match.group(2)
                    if mn not in body:
                        field = f"    void* {mn}; /* AUTO-POINTER */\n" if "ptr" in mn.lower() else f"    long long int {mn};\n"
                        return f"{match.group(1)}{body}{field}{match.group(3)}"
                    return match.group(0)
                types_content = re.sub(pattern, inject_member, types_content)
        write_file(TYPES_HEADER, types_content); fixes += 1

    return fixes, fixed_files
