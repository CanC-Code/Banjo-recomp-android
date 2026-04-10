import os
import re
import glob
import logging
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"
        self.intelligence_level = 3
        self.PHASE_3_MACROS = {
            "OS_IM_NONE": "0x0000", "OS_IM_1": "0x0001", "OS_IM_2": "0x0002", "OS_IM_3": "0x0004",
            "OS_IM_4": "0x0008", "OS_IM_5": "0x0010", "OS_IM_6": "0x0020", "OS_IM_7": "0x0040",
            "OS_IM_ALL": "0x007F", "PFS_ERR_ID_FATAL": "0x10", "PFS_ERR_DEVICE": "0x02",
            "PFS_ERR_CONTRFAIL": "0x01", "PFS_ERR_INVALID": "0x03", "PFS_ERR_EXIST": "0x04",
            "PFS_ERR_NOEXIST": "0x05", "PFS_DATA_ENXIO": "0x06", "ADPCMFSIZE": "9", "ADPCMVSIZE": "16",
            "UNITY_PITCH": "0x8000", "MAX_RATIO": "0xFFFF", "PI_DOMAIN1": "0", "PI_DOMAIN2": "1",
            "DEVICE_TYPE_64DD": "0x06", "LEO_CMD_TYPE_0": "0", "LEO_CMD_TYPE_1": "1", "LEO_CMD_TYPE_2": "2",
            "LEO_SECTOR_MODE": "1", "LEO_TRACK_MODE": "2", "LEO_BM_CTL": "0x05000510", "LEO_BM_CTL_RESET": "0",
            "LEO_ERROR_29": "29", "OS_READ": "0", "OS_WRITE": "1", "OS_MESG_NOBLOCK": "0", "OS_MESG_BLOCK": "1",
            "PI_STATUS_REG": "0x04600010", "PI_DRAM_ADDR_REG": "0x04600000", "PI_CART_ADDR_REG": "0x04600004",
            "PI_RD_LEN_REG": "0x04600008", "PI_WR_LEN_REG": "0x0460000C", "PI_STATUS_DMA_BUSY": "0x01",
            "PI_STATUS_IO_BUSY": "0x02", "PI_STATUS_ERROR": "0x04", "PI_STATUS_INTERRUPT": "0x08",
            "PI_BSD_DOM1_LAT_REG": "0x04600014", "PI_BSD_DOM1_PWD_REG": "0x04600018", "PI_BSD_DOM1_PGS_REG": "0x0460001C",
            "PI_BSD_DOM1_RLS_REG": "0x04600020", "PI_BSD_DOM2_LAT_REG": "0x04600024", "PI_BSD_DOM2_PWD_REG": "0x04600028",
            "PI_BSD_DOM2_PGS_REG": "0x0460002C", "PI_BSD_DOM2_RLS_REG": "0x04600030",
            "G_ON": "1", "G_OFF": "0", "G_RM_AA_ZB_OPA_SURF": "0x00000000", "G_RM_AA_ZB_OPA_SURF2": "0x00000000",
            "G_RM_AA_ZB_XLU_SURF": "0x00000000", "G_RM_AA_ZB_XLU_SURF2": "0x00000000", "G_ZBUFFER": "0x00000001",
            "G_SHADE": "0x00000004", "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
        }
        self.N64_OS_STRUCT_BODIES = {
            "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { int16_t mi[4][4]; int16_t pad; } i; long long int force_align; } Mtx;",
            "OSContStatus": "typedef struct OSContStatus_s { uint16_t type; uint8_t status; uint8_t errno; } OSContStatus;",
            "OSContPad": "typedef struct OSContPad_s { uint16_t button; int8_t stick_x; int8_t stick_y; uint8_t errno; } OSContPad;",
            "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; int32_t validCount; int32_t first; int32_t msgCount; void *msg; } OSMesgQueue;",
            "OSThread": "typedef struct OSThread_s { struct OSThread_s *next; int32_t priority; struct OSThread_s **queue; struct OSThread_s *tlnext; uint16_t state; uint16_t flags; uint64_t id; int fp; long long int context[67]; } OSThread;",
            "OSMesgHdr": "typedef struct { uint16_t type; uint8_t pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
            "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; } OSPiHandle;",
            "OSIoMesg": "typedef struct OSIoMesg_s { void *hdr; void *dramAddr; uint32_t devAddr; uint32_t size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
            "OSDevMgr": "typedef struct OSDevMgr_s { int32_t active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; } OSDevMgr;",
            "OSPfs": "typedef struct OSPfs_s { int32_t channel; uint8_t activebank; uint8_t banks; } OSPfs;",
            "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; uint64_t interval; uint64_t value; struct OSMesgQueue_s *mq; void *msg; } OSTimer;",
            "LookAt": "typedef struct { struct { struct { float x, y, z; float pad; } l[2]; } l; } LookAt;",
            "ADPCM_STATE": "typedef struct { long long int force_align[16]; } ADPCM_STATE;",
            "Acmd": "typedef union { long long int force_align; uint32_t words[2]; } Acmd;",
            "Hilite": "typedef struct { int32_t words[2]; } Hilite;",
            "Light": "typedef struct { int32_t words[2]; } Light;",
            "OSTask": "typedef struct { long long int force_align[64]; } OSTask;",
            "uSprite": "typedef struct { long long int force_align[64]; } uSprite;",
            "CPUState": "typedef struct { long long int force_align[64]; } CPUState;",
        }
        self.PHASE_3_STRUCTS = {
            "Gfx": "typedef struct { uint32_t words[2]; } Gfx;",
            "Vtx": "typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t; typedef union { Vtx_t v; long long int force_align[8]; } Vtx;",
            "OSViMode": "typedef struct OSViMode_s { uint32_t type; uint32_t comRegs[4]; uint32_t fldRegs[2][7]; } OSViMode;",
            "OSViContext": "typedef struct OSViContext_s { uint16_t state; uint16_t retraceCount; void *framep; struct OSViMode_s *modep; uint32_t control; struct OSMesgQueue_s *msgq; void *msg; } OSViContext;",
        }
        self.N64_KNOWN_GLOBALS = {
            "__osPiTable": "struct OSPiHandle_s *__osPiTable;",
            "__osFlashHandle": "struct OSPiHandle_s *__osFlashHandle;",
            "__osSfHandle": "struct OSPiHandle_s *__osSfHandle;",
            "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
            "__osRunQueue": "struct OSThread_s *__osRunQueue;",
            "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
        }

    def bootstrap_n64_types(self, clear_existing=False):
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
        if clear_existing and os.path.exists(self.types_header):
            os.remove(self.types_header)
        if not os.path.exists(self.types_header):
            with open(self.types_header, 'w', encoding='utf-8') as f:
                f.write("#pragma once\n\n/* N64 Recompilation Bridge Header */\n")
        if not os.path.exists(self.stubs_file):
            os.makedirs(os.path.dirname(self.stubs_file), exist_ok=True)
            with open(self.stubs_file, 'w', encoding='utf-8') as f:
                f.write('#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')

    def _inject_primitives_block(self, content: str) -> str:
        primitives_block = """\
#include <stdint.h>
#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
typedef uint8_t  u8; typedef int8_t   s8; typedef uint16_t u16; typedef int16_t  s16;
typedef uint32_t u32; typedef int32_t  s32; typedef uint64_t u64; typedef int64_t  s64;
typedef float    f32; typedef double   f64; typedef int      n64_bool;
typedef int32_t  OSIntMask; typedef uint64_t OSTime; typedef uint32_t OSId;
typedef int32_t  OSPri; typedef void* OSMesg;
#endif
"""
        if "#pragma once" not in content: content = "#pragma once\n" + content
        content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
        return content.replace("#pragma once", f"#pragma once\n{primitives_block}", 1)

    def _handle_math_conflicts(self, content: str) -> str:
        math_block = """
#ifdef __cplusplus
extern "C" {
#endif
float cosf(float angle); float sinf(float angle); float sqrtf(float value);
#ifdef __cplusplus
}
#endif
"""
        if "float cosf(float angle);" not in content:
            content = content.replace("#pragma once", f"#pragma once\n{math_block}", 1)
        return content

    def _handle_missing_functions(self, content: str) -> str:
        sched_yield_decl = """
#ifndef sched_yield_DEFINED
#define sched_yield_DEFINED
#ifdef __cplusplus
extern "C" {
#endif
void sched_yield(void);
#ifdef __cplusplus
}
#endif
#endif
"""
        if "sched_yield_DEFINED" not in content: content += f"\n{sched_yield_decl}\n"
        # Ensure stub is also added to stubs_file
        with open(self.stubs_file, 'a', encoding='utf-8') as sf:
            if "void sched_yield(void) {}" not in open(self.stubs_file).read():
                sf.write("void sched_yield(void) {}\n")
        return content

    def _handle_exceptasm_fixes(self, content: str) -> str:
        # Wrap linkage overrides in guards to prevent C compiler errors (e.g. bss_pad.c)
        linkage_fix = r'#ifdef __cplusplus\nextern "C" struct OSThread_s *\1;\n#else\nextern struct OSThread_s *\1;\n#endif'
        content = re.sub(r'extern struct OSThread_s \*(__osRunQueue);', linkage_fix, content)
        content = re.sub(r'extern struct OSThread_s \*(__osFaultedThread);', linkage_fix, content)
        # Fix context.status member reference (Cast array to uint32_t*)
        content = re.sub(r'__osRunningThread->context\.status', '((uint32_t*)__osRunningThread->context)[0]', content)
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path): return 0
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
        original_content = content

        if "n64_types.h" in file_path:
            content = self._inject_primitives_block(content)
            content = self._handle_math_conflicts(content)
            content = self._handle_missing_functions(content)
            # Inject general linkage and status fixes for the header
            content = self._handle_exceptasm_fixes(content)

        # Apply source-level fixes (like context.status) to all source files
        if file_path.endswith(('.c', '.cpp')):
            content = self._handle_exceptasm_fixes(content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
            return 1
        return 0
