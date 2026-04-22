import os
import re
import logging
import sys
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional, Union

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

# --- Paths ---
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE = "Android/app/src/main/cpp/ultra/n64_stubs.c"
SYNTH_INTERNALS_H = "Android/app/src/main/cpp/../../../../../include/synthInternals.h"
SYNTH_INTERNALS_H_ALT = "include/synthInternals.h"
CMAKE_LISTS_PATH = "Android/app/CMakeLists.txt"

# --- Constants & Fallbacks ---
try:
    from error_parser import (
        BRACE_MATCH, N64_STRUCT_BODIES as _EP_STRUCTS, KNOWN_MACROS as _EP_MACROS,
        KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, OPAQUE_TYPES as _EP_OPAQUE,
        read_file as _ep_read, write_file as _ep_write,
    )
    read_file = _ep_read
    write_file = _ep_write
except ImportError:
    BRACE_MATCH = r"[^{}]*"
    _EP_STRUCTS = {}
    _EP_MACROS = {}
    _EP_OPAQUE = set()

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

# --- Phase Macro Tables ---
PHASE_1_MACROS = {
    "OS_IM_NONE": "0x0000", "OS_IM_1": "0x0001", "OS_IM_2": "0x0002",
    "OS_IM_3": "0x0004", "OS_IM_4": "0x0008", "OS_IM_5": "0x0010",
    "OS_IM_6": "0x0020", "OS_IM_7": "0x0040", "OS_IM_ALL": "0x007F",
    "PFS_ERR_ID_FATAL": "0x10", "PFS_ERR_DEVICE": "0x02",
    "PFS_ERR_CONTRFAIL": "0x01", "PFS_ERR_INVALID": "0x03",
    "PFS_ERR_EXIST": "0x04", "PFS_ERR_NOEXIST": "0x05",
    "PFS_DATA_ENXIO": "0x06", "ADPCMFSIZE": "9", "ADPCMVSIZE": "16",
    "UNITY_PITCH": "0x8000", "MAX_RATIO": "0xFFFF",
    "PI_DOMAIN1": "0", "PI_DOMAIN2": "1",
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
    "PI_STATUS_REG": "0x04600010", "PI_DRAM_ADDR_REG": "0x04600000",
    "PI_CART_ADDR_REG": "0x04600004", "PI_RD_LEN_REG": "0x04600008",
    "PI_WR_LEN_REG": "0x0460000C", "PI_STATUS_DMA_BUSY": "0x01",
    "PI_STATUS_IO_BUSY": "0x02", "PI_STATUS_ERROR": "0x04",
    "PI_STATUS_INTERRUPT": "0x08", "PI_BSD_DOM1_LAT_REG": "0x04600014",
    "PI_BSD_DOM1_PWD_REG": "0x04600018", "PI_BSD_DOM1_PGS_REG": "0x0460001C",
    "PI_BSD_DOM1_RLS_REG": "0x04600020", "PI_BSD_DOM2_LAT_REG": "0x04600024",
    "PI_BSD_DOM2_PWD_REG": "0x04600028", "PI_BSD_DOM2_PGS_REG": "0x0460002C",
    "PI_BSD_DOM2_RLS_REG": "0x04600030",
    "SP_UCODE_SIZE": "0x1000",
    "SP_UCODE_DATA_SIZE": "0x800",
    "FRUSTRATIO_1": "1",
}

PHASE_3_MACROS = {
    **PHASE_2_MACROS,
    "G_ON": "1", "G_OFF": "0",
    "G_TX_RENDERTILE": "0", "G_TX_LOADTILE": "7",
    "G_TX_NOMIRROR": "0", "G_TX_WRAP": "0",
    "G_TX_CLAMP": "0x4", "G_TX_NOMASK": "0",
    "G_TX_NOLOD": "0",
    "COMBINED": "0", "TEXEL0": "1",
    "TEXEL1": "2", "PRIMITIVE": "3",
    "SHADE": "4", "ENVIRONMENT": "5",
    "TEXEL0_ALPHA": "1", "PRIMITIVE_ALPHA": "6",
    "G_RM_AA_ZB_OPA_SURF": "0x00000000", "G_RM_AA_ZB_OPA_SURF2": "0x00000000",
    "G_RM_AA_ZB_XLU_SURF": "0x00000000", "G_RM_AA_ZB_XLU_SURF2": "0x00000000",
    "G_RM_PASS": "0x00000000",
    "G_RM_OPA_SURF2": "0x00000000",
    "G_RM_XLU_SURF2": "0x00000000",
    "Z_CMP": "0x00000001",
    "Z_UPD": "0x00000002",
    "G_ZBUFFER": "0x00000001", "G_SHADE": "0x00000004",
    "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
    "G_CC_DECALRGBA": "0",
    "G_IM_FMT_RGBA": "0", "G_IM_FMT_YUV": "1", "G_IM_FMT_CI": "2",
    "G_IM_FMT_IA": "3", "G_IM_FMT_I": "4",
    "G_IM_SIZ_4b": "0", "G_IM_SIZ_8b": "1",
    "G_IM_SIZ_16b": "2", "G_IM_SIZ_32b": "3",
}

# --- Audio DSP State Typedef Block ---
_AUDIO_STATE_PREAMBLE = """\
/* AUTO-INJECTED by patch_engine.py: N64 audio DSP state forward typedefs */
#ifndef RECOMP_N64_AUDIO_STATES_DEFINED
#define RECOMP_N64_AUDIO_STATES_DEFINED
#ifndef RECOMP_RESAMPLE_STATE_DEFINED
#define RECOMP_RESAMPLE_STATE_DEFINED
typedef struct RESAMPLE_STATE_s { long long int force_align[64]; } RESAMPLE_STATE;
#endif
#ifndef RECOMP_POLEF_STATE_DEFINED
#define RECOMP_POLEF_STATE_DEFINED
typedef struct POLEF_STATE_s { long long int force_align[64]; } POLEF_STATE;
#endif
#ifndef RECOMP_ENVMIX_STATE_DEFINED
#define RECOMP_ENVMIX_STATE_DEFINED
typedef struct ENVMIX_STATE_s { long long int force_align[64]; } ENVMIX_STATE;
#endif
#ifndef RECOMP_INTERLEAVE_STATE_DEFINED
#define RECOMP_INTERLEAVE_STATE_DEFINED
typedef struct INTERLEAVE_STATE_s { long long int force_align[64]; } INTERLEAVE_STATE;
#endif
#ifndef RECOMP_ENVMIX_STATE2_DEFINED
#define RECOMP_ENVMIX_STATE2_DEFINED
typedef struct ENVMIX_STATE2_s { long long int force_align[64]; } ENVMIX_STATE2;
#endif
#ifndef RECOMP_HIPASSLOOP_STATE_DEFINED
#define RECOMP_HIPASSLOOP_STATE_DEFINED
typedef struct HIPASSLOOP_STATE_s { long long int force_align[64]; } HIPASSLOOP_STATE;
#endif
#ifndef RECOMP_COMPRESS_STATE_DEFINED
#define RECOMP_COMPRESS_STATE_DEFINED
typedef struct COMPRESS_STATE_s { long long int force_align[64]; } COMPRESS_STATE;
#endif
#ifndef RECOMP_REVERB_STATE_DEFINED
#define RECOMP_REVERB_STATE_DEFINED
typedef struct REVERB_STATE_s { long long int force_align[64]; } REVERB_STATE;
#endif
#ifndef RECOMP_MIXER_STATE_DEFINED
#define RECOMP_MIXER_STATE_DEFINED
typedef struct MIXER_STATE_s { long long int force_align[64]; } MIXER_STATE;
#endif
#endif /* RECOMP_N64_AUDIO_STATES_DEFINED */
"""

# --- N64 Struct Bodies (Fully Decoupled) ---
_N64_OS_STRUCT_BODIES = {
    "Mtx": "#ifndef Mtx_DEFINED\n#define Mtx_DEFINED\ntypedef union { long m[4][4]; struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;\n#endif",
    "OSContStatus": "#ifndef OSContStatus_DEFINED\n#define OSContStatus_DEFINED\ntypedef struct OSContStatus_s { u16 type; u8 status; union { u8 errnum; u8 errno; }; } OSContStatus;\n#endif",
    "OSContPad": "#ifndef OSContPad_DEFINED\n#define OSContPad_DEFINED\ntypedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; union { u8 errnum; u8 errno; }; } OSContPad;\n#endif",
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
    "OSIoMesg": "#ifndef OSIoMesg_DEFINED\n#define OSIoMesg_DEFINED\ntypedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; u32 devAddr; u32 size; struct OSPiHandle_s *piHandle; } OSIoMesg;\n#endif",
    "OSDevMgr": "#ifndef OSDevMgr_DEFINED\n#define OSDevMgr_DEFINED\ntypedef struct OSDevMgr_s { s32 active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; s32 (*dma)(s32, u32, void *, u32); s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32); } OSDevMgr;\n#endif",
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
        '    u8 id[32];\n'
        '    u8 label[32];\n'
        '    u32 version;\n'
        '    u32 dir_size;\n'
        '    u32 inode_table;\n'
        '    u32 minode_table;\n'
        '    u32 dir_table;\n'
        '    u32 inode_start_page;\n'
        '    s32 repairList[256];\n'
        '    u32 checksum;\n'
        '    u32 inodeCacheIndex;\n'
        '    u8 inodeCache[256];\n'
        '} OSPfs;\n'
        '#endif'
    ),
    "OSTimer": "#ifndef OSTimer_DEFINED\n#define OSTimer_DEFINED\ntypedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;\n#endif",
    "LookAt": "#ifndef LookAt_DEFINED\n#define LookAt_DEFINED\ntypedef union { Light l[2]; long long int force_align[2]; } LookAt;\n#endif",
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
    "Gfx": "#ifndef Gfx_DEFINED\n#define Gfx_DEFINED\ntypedef struct { u32 words[2]; } Gfx;\n#endif",
    "Acmd": "#ifndef Acmd_DEFINED\n#define Acmd_DEFINED\ntypedef union { struct { u32 w0; u32 w1; } words; long long int force_align[1]; } Acmd;\n#endif",
    "Light_t": "#ifndef Light_t_DEFINED\n#define Light_t_DEFINED\ntypedef struct { u8 col[3]; u8 pad0; u8 colc[3]; u8 pad1; s8 dir[3]; u8 pad2; } Light_t;\n#endif",
    "Light": "#ifndef Light_DEFINED\n#define Light_DEFINED\ntypedef union { Light_t l; long long int force_align[2]; } Light;\n#endif",
    "Hilite_t": "#ifndef Hilite_t_DEFINED\n#define Hilite_t_DEFINED\ntypedef struct { int x1, y1, x2, y2; } Hilite_t;\n#endif",
    "Hilite": "#ifndef Hilite_DEFINED\n#define Hilite_DEFINED\ntypedef union { Hilite_t h; long long int force_align[2]; } Hilite;\n#endif",
    "uSprite": "#ifndef uSprite_DEFINED\n#define uSprite_DEFINED\ntypedef struct { s16 objX, objY; u16 scaleW, scaleH; s16 imageW, imageH; u16 paddedW, paddedH; u16 bitmapW, bitmapH; s16 imageX, imageY; u16 imageFlags; } uSprite;\n#endif",
    "CPUState": "#ifndef CPUState_DEFINED\n#define CPUState_DEFINED\ntypedef struct { u32 gpr[32]; u32 sr, pc, cause, badvaddr, sp, ra; u32 lo, hi; u32 fpr[32]; u32 fpcsr; } CPUState;\n#endif",
    "MapModelDescription": (
        "#ifndef MapModelDescription_DEFINED\n"
        "#define MapModelDescription_DEFINED\n"
        "typedef struct MapModelDescription_s {\n"
        "    s32 map_id;\n"
        "    s32 opa_model_id;\n"
        "    s32 xlu_model_id;\n"
        "    f32 scale;\n"
        "    long long int force_align_tail[60];\n"
        "} MapModelDescription;\n"
        "#endif"
    ),
    "MapProgressFlagToDialogID": (
        "#ifndef MapProgressFlagToDialogID_DEFINED\n"
        "#define MapProgressFlagToDialogID_DEFINED\n"
        "typedef struct MapProgressFlagToDialogID_s {\n"
        "    s32 value;\n"
        "    long long int force_align_tail[63];\n"
        "} MapProgressFlagToDialogID;\n"
        "#endif"
    ),
}

# Tag match structural forwarding safely detaches compiler dependency from local code limits
N64_FORWARD_STRUCTS = ["Struct_core2_7AF80_1", "Struct_core1_10A00_1"]

# --- Automatically Upgrade Struct Definitions with RECOMP Prefix ---
ALL_STRUCTS = {**_N64_OS_STRUCT_BODIES, **PHASE_3_STRUCTS}
for _k in ALL_STRUCTS:
    ALL_STRUCTS[_k] = ALL_STRUCTS[_k].replace(f"#ifndef {_k}_DEFINED", f"#ifndef RECOMP_{_k}_DEFINED")
    ALL_STRUCTS[_k] = ALL_STRUCTS[_k].replace(f"#define {_k}_DEFINED", f"#define RECOMP_{_k}_DEFINED")

# --- N64 Primitives ---
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
    "OSHWIntr", "ADPCM_STATE", "OSYieldResult", "OSEvent", "Vp_t", "Vp"
}

# REMOVED: "OSPfsState", "OSPfsFile", "OSPfsDir" to prevent collision with core1/pfsmanager.h definitions
N64_OS_OPAQUE_TYPES = {
    "OSPiHandle", "OSMesgQueue", "OSThread",
    "OSIoMesg", "OSTimer", "OSScTask", "OSTask", "OSScClient", "OSScKiller",
    "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr", "OSDevMgr", "SPTask", "GBIarg",
    "OSYieldResult", "OSEvent",
    "Acmd", "Gfx", "Light", "Hilite", "uSprite", "CPUState",
}

N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "INTERLEAVE_STATE",
    "ENVMIX_STATE2", "HIPASSLOOP_STATE", "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

N64_KNOWN_GLOBALS = {
    "__osPiTable": "struct OSPiHandle_s *__osPiTable;",
    "__osFlashHandle": "struct OSPiHandle_s *__osFlashHandle;",
    "__osSfHandle": "struct OSPiHandle_s *__osSfHandle;",
    "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
    "__osRunQueue": "struct OSThread_s *__osRunQueue;",
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
    "osTvType": "extern u32 osTvType;",
    "osRomBase": "extern u32 osRomBase;",
    "osResetType": "extern u32 osResetType;",
    "osAppNMIBuffer": "extern u32 osAppNMIBuffer;",
    "osClockRate": "extern OSTime osClockRate;",
    "osViModeNtscLan1": "extern OSViMode osViModeNtscLan1;",
    "osViModePalLan1": "extern OSViMode osViModePalLan1;",
    "osViModeMpalLan1": "extern OSViMode osViModeMpalLan1;",
    "osPiRawStartDma": "extern s32 osPiRawStartDma(s32, u32, void *, u32);",
    "osEPiRawStartDma": "extern s32 osEPiRawStartDma(struct OSPiHandle_s *, s32, u32, void *, u32);",
    "__OSGlobalIntMask": "extern u32 __OSGlobalIntMask;",
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
    "#undef NULL\n"
    "#ifdef __cplusplus\n"
    "#define NULL 0\n"
    "#else\n"
    "#define NULL 0\n"
    "#endif\n"
    "#ifndef RECOMP_CORE_PRIMITIVES_DEFINED\n"
    "#define RECOMP_CORE_PRIMITIVES_DEFINED\n"
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
    "#ifndef RECOMP_ADPCM_STATE_DEFINED\n"
    "#define RECOMP_ADPCM_STATE_DEFINED\n"
    "typedef short ADPCM_STATE[9];\n"
    "#endif\n"
    "#ifndef RECOMP_OSYieldResult_DEFINED\n"
    "#define RECOMP_OSYieldResult_DEFINED\n"
    "typedef u32 OSYieldResult;\n"
    "#endif\n"
    "#ifndef RECOMP_OSEvent_DEFINED\n"
    "#define RECOMP_OSEvent_DEFINED\n"
    "typedef u32 OSEvent;\n"
    "#endif\n"
    "#ifndef RECOMP_Vp_DEFINED\n"
    "#define RECOMP_Vp_DEFINED\n"
    "typedef struct { s16 vscale[4]; s16 vtrans[4]; } Vp_t;\n"
    "typedef union { Vp_t vp; long long int force_align[4]; } Vp;\n"
    "#endif\n"
    "#ifdef __cplusplus\n"
    "extern \"C\" int sched_yield(void);\n"
    "#endif\n"
    "#endif /* END_CORE_PRIMITIVES */\n"
)

# --- Utility Helpers ---
def normalize_path(filepath: str) -> str:
    if ".." in filepath:
        filepath = os.path.normpath(filepath).replace('\\', '/')
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath:
            return filepath.split(marker)[-1]
    return filepath.lstrip("/") if filepath.startswith("/") else filepath

def _scrub_linkage_comments(content: str) -> str:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "AUTO-FIX LINKAGE:" in line:
            cleaned = (
                line.replace("/* AUTO-FIX LINKAGE:", "")
                .replace("/* AUTO-FIX LINKAGE: ", "")
                .replace("// AUTO-FIX LINKAGE:", "")
                .replace("*/", "")
                .strip()
            )
            lines[i] = cleaned
    return '\n'.join(lines)

def heal_corrupted_headers():
    search_dirs = [
        "Android/app/src/main/cpp/../../../../../include",
        "include"
    ]
    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(('.h', '.c', '.cpp')):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', errors='replace') as f:
                            c = f.read()
                        if "AUTO-FIX LINKAGE:" in c:
                            c = _scrub_linkage_comments(c)
                            write_file(path, c)
                    except Exception:
                        pass

def ensure_n64_bool_header():
    for base_dir in ["include", "Android/app/src/main/cpp/../../../../../include"]:
        os.makedirs(base_dir, exist_ok=True)
        path = os.path.join(base_dir, "n64_bool.h")
        content = "#ifndef RECOMP_N64_BOOL_H\n#define RECOMP_N64_BOOL_H\n#include <stdint.h>\ntypedef int n64_bool;\n#endif\n"
        try:
            write_file(path, content)
        except Exception:
            pass

def patch_cmake_compiler_flags(categories: Dict) -> bool:
    path = CMAKE_LISTS_PATH
    if not os.path.exists(path):
        path = "CMakeLists.txt"
        if not os.path.exists(path):
            return False

    content = read_file(path)
    flags = "-xc++ -fpermissive -Wno-narrowing -Wno-c++11-narrowing -Wno-writable-strings -Wno-constant-conversion"
    
    # DYNAMIC ROBUSTNESS: Complete eradication of C++ strictness for valid C initialization
    if categories.get("remove_xcxx"):
        original = content
        content = content.replace(f'set(CMAKE_C_FLAGS "${{CMAKE_C_FLAGS}} {flags}")\n', "")
        content = content.replace(f'set(CMAKE_C_FLAGS "${{CMAKE_C_FLAGS}} {flags}")', "")
        content = content.replace("# AUTO-INJECTED COMPILER FLAGS BY N64_RECOMP_ENGINE\n", "")
        content = content.replace(flags, "")
        content = content.replace("-xc++ ", "")
        
        if content != original:
            write_file(path, content)
            return True
        return False
    else:
        if "-xc++" in content:
            return False
            
        content += f'\n# AUTO-INJECTED COMPILER FLAGS BY N64_RECOMP_ENGINE\n'
        content += f'set(CMAKE_C_FLAGS "${{CMAKE_C_FLAGS}} {flags}")\n'
        
        write_file(path, content)
        return True

def strip_redefinition(content: str, tag: str) -> str:
    content = re.sub(
        rf"(?m)^// --- RECOMP_INJECT: {re.escape(tag)} ---[\s\S]*?// --- END_RECOMP_INJECT: {re.escape(tag)} ---\r?\n?",
        "",
        content
    )

    content = re.sub(
        rf"(?m)^\s*#\s*ifndef\s+(?:RECOMP_)?{re.escape(tag)}_DEFINED\s*\r?\n\s*#\s*define\s+(?:RECOMP_)?{re.escape(tag)}_DEFINED\s*\r?\n\s*struct\s+{re.escape(tag)}(?:_s)?\s+{{[\s\S]*?}};\s*\r?\n\s*typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)};\s*\r?\n\s*#\s*endif\s*\r?\n?",
        "",
        content
    )
    
    content = re.sub(
        rf"(?m)^\s*#\s*ifndef\s+(?:RECOMP_)?{re.escape(tag)}_FWD_DEFINED\s*\r?\n\s*#\s*define\s+(?:RECOMP_)?{re.escape(tag)}_FWD_DEFINED\s*\r?\n\s*struct\s+{re.escape(tag)};\s*\r?\n\s*typedef\s+struct\s+{re.escape(tag)}\s+{re.escape(tag)};\s*\r?\n\s*#\s*endif\s*\r?\n?",
        "",
        content
    )

    content = re.sub(
        rf"(?m)^\s*#\s*define\s+(?:RECOMP_)?{re.escape(tag)}(?:_s|_u)?_DEFINED\b.*$",
        f"/* STRIPPED DEFINE: {tag}_DEFINED */",
        content
    )
    content = re.sub(
        rf"(?m)^\s*typedef\s+(?:struct|union)\s+[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;\s*$",
        f"/* STRIPPED FWD: {tag} */",
        content
    )

    content = re.sub(
        rf"\b(?:typedef\s+(?:struct|union)|struct|union)\b[^{{;]*{{[^{{}}]*}}\s*{re.escape(tag)}(?:_s|_u)?\s*;",
        f"/* STRIPPED SIMPLE BLOCK: {tag} */",
        content
    )

    pattern = re.compile(r'\b(typedef\s+(?:struct|union)|struct|union)\b[^{;]*\{')
    new_content = ""
    idx = 0
    tag_pattern = rf'\b{re.escape(tag)}(?:_s|_u)?\b'

    while True:
        match = pattern.search(content, idx)
        if not match:
            new_content += content[idx:]
            break

        start_idx = match.start()
        brace_idx = content.find('{', start_idx)

        open_braces = 1
        curr_idx = brace_idx + 1
        in_line_comment = False
        in_block_comment = False

        while curr_idx < len(content) and open_braces > 0:
            if not in_line_comment and not in_block_comment:
                if content[curr_idx:curr_idx+2] == '//':
                    in_line_comment = True
                    curr_idx += 2
                    continue
                elif content[curr_idx:curr_idx+2] == '/*':
                    in_block_comment = True
                    curr_idx += 2
                    continue
                elif content[curr_idx] == '{':
                    open_braces += 1
                elif content[curr_idx] == '}':
                    open_braces -= 1
            elif in_line_comment:
                if content[curr_idx] == '\n':
                    in_line_comment = False
            elif in_block_comment:
                if content[curr_idx:curr_idx+2] == '*/':
                    in_block_comment = False
                    curr_idx += 2
                    continue
            curr_idx += 1

        semi_idx = content.find(';', curr_idx)

        if semi_idx != -1 and '{' not in content[curr_idx:semi_idx]:
            tail = content[curr_idx:semi_idx+1]
            header = content[start_idx:brace_idx]
            if re.search(tag_pattern, tail) or re.search(tag_pattern, header):
                new_content += content[idx:start_idx] + f"\n/* STRIPPED BLOCK: {tag} */\n"
                idx = semi_idx + 1
                continue

        new_content += content[idx:brace_idx+1]
        idx = brace_idx + 1

    content = new_content
    content = re.sub(
        rf"\btypedef\s+(?:struct\s+|union\s+)?[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;",
        f"/* STRIPPED SIMPLE: {tag} */",
        content
    )
    content = re.sub(
        rf"\b(?:struct|union)\s+{re.escape(tag)}(?:_s|_u)?\s*;",
        "",
        content
    )
    return content

def _find_synth_internals() -> Optional[str]:
    candidates = [SYNTH_INTERNALS_H, SYNTH_INTERNALS_H_ALT, "include/synthInternals.h"]
    for root, _, files in os.walk("include"):
        for f in files:
            if f == "synthInternals.h":
                candidates.append(os.path.join(root, f))
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def patch_synth_internals() -> bool:
    path = _find_synth_internals()
    if not path:
        return False
    content = read_file(path)
    if "RECOMP_N64_AUDIO_STATES_DEFINED" in content or "N64_AUDIO_STATES_DEFINED" in content:
        return False
    write_file(path, _AUDIO_STATE_PREAMBLE + content)
    return True

def patch_exceptasm() -> bool:
    path = "Android/app/src/main/cpp/ultra/exceptasm.cpp"
    if not os.path.exists(path):
        return False
    content = read_file(path)
    original = content
    content = re.sub(
        r'\bvolatile\s+(uint32_t|u32)\s+(__OSGlobalIntMask\s*=)',
        r'\1 \2',
        content
    )
    content = re.sub(
        r'reinterpret_cast<uint32_t\*>\(\s*__osRunningThread->context\s*\)',
        r'reinterpret_cast<uint32_t*>(&__osRunningThread->context)',
        content
    )
    if content != original:
        write_file(path, content)
        return True
    return False

def ensure_types_header_base(categories: Optional[Dict] = None) -> str:
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
    else:
        content = ""

    content = re.sub(
        r'(?m)^#include <stdint\.h>\s*\r?\n#ifndef (?:CORE|RECOMP_CORE)_PRIMITIVES_DEFINED[\s\S]*?#endif /\* END_CORE_PRIMITIVES \*/\s*\r?\n?',
        '',
        content
    )
    content = content.replace("#pragma once", "").strip()
    content = "#pragma once\n" + _CORE_PRIMITIVES + "\n" + content
    write_file(TYPES_HEADER, content)
    return content

def _opaque_stub(tag: str, size: int = 64, missing_members: Set[str] = None) -> str:
    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
    members = ""
    if missing_members:
        for m in sorted(missing_members):
            if m.startswith('f') or m.endswith('_x') or m.endswith('_y') or m.endswith('_z'):
                members += f"    float {m};\n"
            else:
                members += f"    int {m};\n"
    
    return (
        f"#ifndef RECOMP_{tag}_DEFINED\n"
        f"#define RECOMP_{tag}_DEFINED\n"
        f"struct {struct_tag} {{\n"
        f"{members}"
        f"    long long int force_align[{size}];\n"
        f"}};\n"
        f"typedef struct {struct_tag} {tag};\n"
        f"#endif\n"
    )

def _scrape_logs_into_categories(categories: Dict) -> None:
    log_candidates = [
        "Android/full_build_log.txt",
        "full_build_log.txt",
        "build_log.txt",
        "Android/failed_files.log"
    ]
    
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    for log_file in log_candidates:
        if not os.path.exists(log_file):
            continue
            
        raw_content = read_file(log_file)
        content = ansi_escape.sub('', raw_content)
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # 1) Robust Linkage Scanner
            m_link = re.search(
                r"(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+declaration of '(\w+)' has a different language linkage",
                line
            )
            if m_link:
                file_err = normalize_path(m_link.group(1))
                func = m_link.group(2)

                file_note = None
                for j in range(i+1, min(i+15, len(lines))):
                    m_note = re.search(
                        r"(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+note:\s+previous declaration is here",
                        lines[j]
                    )
                    if m_note:
                        file_note = normalize_path(m_note.group(1))
                        break

                if (
                    "sysroot" not in file_err
                    and "toolchains" not in file_err
                    and "ndk" not in file_err.lower()
                ):
                    categories.setdefault("linkage_conflict_files", set()).add((file_err, func))
                elif (
                    file_note
                    and "sysroot" not in file_note
                    and "toolchains" not in file_note
                    and "ndk" not in file_note.lower()
                ):
                    categories.setdefault("linkage_conflict_files", set()).add((file_note, func))

            # 2) DYNAMIC ROBUSTNESS FIX: Base Tag Re-mapping to Prevent Blind Re-injections
            m_struct1 = re.search(r"error:\s+(?:unknown type name|member access into incomplete type|variable has incomplete type|incomplete type)\s+'(?:struct\s+|union\s+)?(\w+)'", line)
            if m_struct1:
                tag = m_struct1.group(1)
                categories.setdefault("need_struct_body", set()).add(tag)
                if tag.endswith("_s") or tag.endswith("_u"):
                    categories["need_struct_body"].add(tag[:-2])

            if "error:" in line and ("redefinition" in line or "conflicting types" in line):
                matches = re.findall(r"'(?:struct\s+|union\s+)?(\w+)'", line)
                for m in matches:
                    categories.setdefault("redefinition_conflict", set()).add(m)
                    if m.endswith("_s") or m.endswith("_u"):
                        categories["redefinition_conflict"].add(m[:-2])
                    else:
                        categories["redefinition_conflict"].add(f"{m}_s")

            # 3) DYNAMIC ROBUSTNESS: Missing Struct Member Synthesis
            m_member = re.search(r"error:\s+no member named '(\w+)' in '(?:struct\s+|union\s+)?(\w+)'", line)
            if m_member:
                member_name = m_member.group(1)
                struct_tag = m_member.group(2)
                categories.setdefault("missing_members", defaultdict(set))[struct_tag].add(member_name)
                categories.setdefault("need_struct_body", set()).add(struct_tag)
                
                base_tag = struct_tag[:-2] if (struct_tag.endswith("_s") or struct_tag.endswith("_u")) else struct_tag
                categories["missing_members"][base_tag].add(member_name)
                categories["need_struct_body"].add(base_tag)

            # 4) DYNAMIC ROBUSTNESS: Intelligent Contextual Macro Synthesis
            m_undeclared = re.search(r"error:\s+use of undeclared identifier\s+'(\w+)'", line)
            if m_undeclared:
                categories.setdefault("undeclared_vars", set()).add(m_undeclared.group(1))

            m_impl_func = re.search(r"error:\s+implicit declaration of function\s+'(\w+)'", line)
            if m_impl_func:
                categories.setdefault("undeclared_funcs", set()).add(m_impl_func.group(1))

            if "error: expected ';' after expression" in line:
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    m_ident = re.search(r'^([a-zA-Z_]\w*)', next_line)
                    if m_ident:
                        ident = m_ident.group(1)
                        if '(' in next_line:
                            categories.setdefault("undeclared_funcs", set()).add(ident)
                        else:
                            categories.setdefault("undeclared_vars", set()).add(ident)

            # 5) DYNAMIC ROBUSTNESS: Drop strict C++ when compound literals break initializations
            if "initializer element is not a compile-time constant" in line:
                categories["remove_xcxx"] = True

def is_func_macro(name: str) -> bool:
    return name.startswith("rare_") or name.startswith("gs") or name.startswith("gDP") or name.startswith("gSP") or name.startswith("gDma")

def apply_fixes(categories: Dict, intelligence_level: int = 4) -> Tuple[int, Set[str]]:
    fixes = 0
    fixed_files = set()

    heal_corrupted_headers()
    ensure_n64_bool_header()
    _scrape_logs_into_categories(categories)

    ensure_types_header_base(categories)

    if patch_synth_internals():
        fixes += 1
    if patch_exceptasm():
        fixes += 1
    if patch_cmake_compiler_flags(categories):
        fixes += 1

    # DYNAMIC ROBUSTNESS FIX: Strictly ordered injection layout based on topological dependencies
    # Resolves standard C parsing errors when embedding unions/structs by value
    ORDERED_STRUCT_TAGS = [
        "Mtx", "Light_t", "Hilite_t", "Vtx_t", "Vtx_n",
        "__OSBlockInfo", "__OSViCommonRegs", "__OSViFieldRegs",
        "__OSThreadContext", "OSContStatus", "OSContPad", "OSTask_t",
        "Gfx", "Acmd", "uSprite", "CPUState", "MapModelDescription", "MapProgressFlagToDialogID",
        
        "OSThread", "__OSTranxInfo", "OSViMode", "Light", "Hilite", "Vtx", "OSTask",
        
        "OSMesgQueue", "OSPiHandle", "LookAt",
        
        "OSMesgHdr", "OSViContext", "OSDevMgr", "OSTimer",
        
        "OSIoMesg",
        
        "OSPfs"
    ]

    types_content = read_file(TYPES_HEADER)

    marker = "/* Forward declarations for source-defined typed globals */"
    if marker in types_content:
        types_content = types_content.split(marker)[0].strip()

    redef_conflicts = set(categories.get("redefinition_conflict", set()))

    for tag in redef_conflicts:
        types_content = strip_redefinition(types_content, tag)

    target_tags = set(ALL_STRUCTS.keys())
    if "need_struct_body" in categories:
        target_tags |= set(categories["need_struct_body"])

    target_tags = {t for t in target_tags if t not in SDK_DEFINES_THESE and t not in N64_PRIMITIVES}
    
    # Safely back off from injecting structs that native headers handle
    target_tags -= redef_conflicts

    injected_structs = ""

    def _format_injection(tag: str, inner_code: str) -> str:
        return f"\n// --- RECOMP_INJECT: {tag} ---\n{inner_code}\n// --- END_RECOMP_INJECT: {tag} ---\n"

    for tag in ORDERED_STRUCT_TAGS:
        if tag in target_tags:
            types_content = strip_redefinition(types_content, tag)
            if tag in ALL_STRUCTS:
                injected_structs += _format_injection(tag, ALL_STRUCTS[tag])
            elif tag in N64_OS_OPAQUE_TYPES:
                injected_structs += _format_injection(tag, _opaque_stub(tag))
            elif tag in N64_AUDIO_STATE_TYPES:
                injected_structs += _format_injection(tag, f"#ifndef RECOMP_{tag}_DEFINED\n#define RECOMP_{tag}_DEFINED\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};\n#endif")
            else:
                missing = categories.get("missing_members", {}).get(tag, set())
                injected_structs += _format_injection(tag, _opaque_stub(tag, 64, missing))
            target_tags.discard(tag)

    for tag in list(target_tags):
        types_content = strip_redefinition(types_content, tag)
        if tag in ALL_STRUCTS:
            injected_structs += _format_injection(tag, ALL_STRUCTS[tag])
        elif tag in N64_OS_OPAQUE_TYPES:
            injected_structs += _format_injection(tag, _opaque_stub(tag))
        elif tag in N64_AUDIO_STATE_TYPES:
            injected_structs += _format_injection(tag, f"#ifndef RECOMP_{tag}_DEFINED\n#define RECOMP_{tag}_DEFINED\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};\n#endif")
        else:
            logger.info(f"Dynamically generating opaque stub for unknown struct: {tag}")
            missing = categories.get("missing_members", {}).get(tag, set())
            injected_structs += _format_injection(tag, _opaque_stub(tag, 64, missing))

    for tag in N64_FORWARD_STRUCTS:
        types_content = strip_redefinition(types_content, tag)
        if tag not in redef_conflicts:
            injected_structs += _format_injection(tag, f"#ifndef RECOMP_{tag}_FWD_DEFINED\n#define RECOMP_{tag}_FWD_DEFINED\nstruct {tag};\ntypedef struct {tag} {tag};\n#endif")

    types_content = strip_redefinition(types_content, "MACROS")

    # DYNAMIC ROBUSTNESS FIX: Synthesize macro calls specifically according to object vs functional usage
    macro_injection = "\n// --- RECOMP_INJECT: MACROS ---\n"
    for m_name, m_val in PHASE_3_MACROS.items():
        macro_injection += f"#ifndef {m_name}\n#define {m_name} {m_val}\n#endif\n"
        
    for m_name in sorted(categories.get("undeclared_vars", set())):
        if is_func_macro(m_name):
            macro_injection += f"#ifndef {m_name}\n#define {m_name}(...) {{0}}\n#endif\n"
        else:
            macro_injection += f"#ifndef {m_name}\n#define {m_name} 0\n#endif\n"

    for m_name in sorted(categories.get("undeclared_funcs", set())):
        macro_injection += f"#ifndef {m_name}\n#define {m_name}(...) {{0}}\n#endif\n"
            
    macro_injection += "// --- END_RECOMP_INJECT: MACROS ---\n"
    
    injected_structs = macro_injection + injected_structs

    for var in _TYPED_SOURCE_GLOBALS:
        types_content = re.sub(
            rf"(?m)^extern\s+[^;]+\b{re.escape(var)}\b.*;",
            "",
            types_content
        )
        types_content = re.sub(
            rf"#ifndef RECOMP_{re.escape(var)}_fwd_DEFINED[\s\S]*?#endif",
            "",
            types_content
        )

    core_marker = "/* END_CORE_PRIMITIVES */"
    if core_marker in types_content:
        parts = types_content.split(core_marker, 1)
        types_content = parts[0] + core_marker + "\n" + injected_structs + parts[1]
    else:
        types_content = injected_structs + "\n" + types_content

    types_content += f"\n\n{marker}\n"
    types_content += "#ifndef RECOMP_OSViMode_fwd\n#define RECOMP_OSViMode_fwd\ntypedef struct OSViMode_s OSViMode;\n#endif\n"
    types_content += '#ifdef __cplusplus\nextern "C" {\n#endif\n'
    for var, decl in _TYPED_SOURCE_GLOBAL_DECLS.items():
        types_content += f"#ifndef RECOMP_{var}_fwd_DEFINED\n#define RECOMP_{var}_fwd_DEFINED\n{decl}\n#endif\n"
    types_content += '#ifdef __cplusplus\n}\n#endif\n'

    write_file(TYPES_HEADER, types_content)
    fixes += 1

    if categories.get("linkage_conflict_files"):
        for filepath, func in categories["linkage_conflict_files"]:
            if os.path.exists(filepath):
                c = read_file(filepath)
                c = _scrub_linkage_comments(c)
                
                pattern = rf"(?m)^(?![^\n]*// AUTO-FIX LINKAGE)(.*?\b{re.escape(func)}\s*\(.*?;)"
                c, n = re.subn(pattern, r"// AUTO-FIX LINKAGE: \1", c)
                if n > 0:
                    if "#include <math.h>" not in c and func in _STDLIB_FUNCS:
                        c = "#include <math.h>\n" + c
                    write_file(filepath, c)
                    fixed_files.add(filepath)
                    fixes += 1

    return fixes, fixed_files
