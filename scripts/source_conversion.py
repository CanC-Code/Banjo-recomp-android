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

        self.SDK_DEFINES_THESE = {
            "Actor", "OSScTask", "sChVegetable", "LetterFloorTile",
            "MapProgressFlagToDialogID", "n64_bool"
        }

        self.STANDARD_TYPES = {
            "uint8_t", "int8_t", "uint16_t", "int16_t", "uint32_t", "int32_t",
            "uint64_t", "int64_t", "size_t", "intptr_t", "uintptr_t", "ptrdiff_t",
            "bool", "_Bool", "wchar_t", "char16_t", "char32_t", "float", "double",
            "void", "char", "short", "int", "long", "unsigned", "signed",
            "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64", "n64_bool"
        }

        self.POSIX_RESERVED_NAMES = { ... }  # unchanged

        # ---------------------------------------------------------------------------
        # Macros & Struct Dicts (FINAL TUNED)
        # ---------------------------------------------------------------------------
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
            "G_SHADE": "0x00000004", "G_CULL_BACK": "0x00002000", "G_CULL_BOTH": "0x00003000",
            "G_FOG": "0x00010000", "G_LIGHTING": "0x00020000", "G_TEXTURE_GEN": "0x00040000",
            "G_TEXTURE_GEN_LINEAR": "0x00080000", "G_LOD": "0x00100000", "G_SHADING_SMOOTH": "0x00200000",
            "G_CC_SHADE": "0x00000000",
            "OS_CLOCK_RATE": "62500000LL",
            "OS_APP_NMI_BUFSIZE": "64",
        }

        self.N64_OS_STRUCT_BODIES = {
            # ... (all previous bodies unchanged except OSThread)
            "OSThread": """typedef struct OSThread_s {
    struct OSThread_s *next;
    int32_t priority;
    struct OSThread_s **queue;
    struct OSThread_s *tlnext;
    uint16_t state;
    uint16_t flags;
    uint64_t id;
    int fp;
    long long int context[67];   /* RAW ARRAY - fixes both exceptasm.cpp cast and createthread.c access */
} OSThread;""",
            # ... rest of bodies unchanged
            "LetterFloorTile": """typedef struct LetterFloorTile_s {
    void *meshId;
    int state;
    float timeDeltaSum;
} LetterFloorTile;""",
            "sChVegetable": "typedef struct sChVegetable_s { long long int force_align[64]; } sChVegetable;",
            "MapProgressFlagToDialogID": """typedef struct MapProgressFlagToDialogID_s {
    int16_t key;
    int16_t value;
} MapProgressFlagToDialogID;""",
        }

        self.N64_KNOWN_GLOBALS = {
            "__osPiTable": "struct OSPiHandle_s *__osPiTable;",
            "__osFlashHandle": "struct OSPiHandle_s *__osFlashHandle;",
            "__osSfHandle": "struct OSPiHandle_s *__osSfHandle;",
            "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
            "__osRunQueue": "struct OSThread_s *__osRunQueue;",
            "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
            "__OSGlobalIntMask": "volatile uint32_t __OSGlobalIntMask;",
            "osTvType": "uint32_t osTvType;",
            "osRomBase": "uint32_t osRomBase;",
            "osResetType": "uint32_t osResetType;",
            "osAppNMIBuffer": "uint32_t osAppNMIBuffer[OS_APP_NMI_BUFSIZE];",
            "__osEventStateTab": "OSMesg __osEventStateTab[16];",
            "osPiRawStartDma": "int32_t osPiRawStartDma(int32_t direction, uint32_t devAddr, void *dramAddr, uint32_t size);",
            "osEPiRawStartDma": "int32_t osEPiRawStartDma(struct OSPiHandle_s *piHandle, int32_t direction, uint32_t devAddr, void *dramAddr, uint32_t size);",
            "osClockRate": "OSTime osClockRate;",
        }

        self.rules = []
        self.dynamic_categories = defaultdict(set)

    # ... (all helper methods unchanged until apply_to_file)

    def _inject_primitives_block(self, content: str) -> str:
        if "CORE_PRIMITIVES_DEFINED" in content:
            return content
        primitives_block = """\
#include <stdint.h>

#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
typedef uint8_t  u8; typedef int8_t   s8; typedef uint16_t u16; typedef int16_t  s16;
typedef uint32_t u32; typedef int32_t  s32; typedef uint64_t u64; typedef int64_t  s64;
typedef float    f32; typedef double   f64; typedef int      n64_bool;
typedef int32_t  OSIntMask; typedef uint64_t OSTime; typedef uint32_t OSId;
typedef int32_t  OSPri; typedef void* OSMesg;

#ifdef __cplusplus
extern "C" {
#endif
float cosf(float);
float sinf(float);
float sqrtf(float);
int sched_yield(void);
#ifdef __cplusplus
}
#endif
#endif
"""
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
        return content.replace("#pragma once", f"#pragma once\n{primitives_block}", 1)

    def _inject_macros_block(self, content: str) -> str:
        """Inject ALL macros right after primitives so audio/GBI files see them early."""
        if "#define ADPCMFSIZE" in content:
            return content
        macro_block = "\n".join(f"#define {k} {v}" for k, v in self.PHASE_3_MACROS.items())
        return content + f"\n/* === EARLY MACROS === */\n{macro_block}\n"

    def _handle_exceptasm_fixes(self, content: str) -> str:
        linkage_fix = (
            '#ifdef __cplusplus\n'
            'extern "C" struct OSThread_s *\\1;\n'
            '#else\n'
            'extern struct OSThread_s *\\1;\n'
            '#endif'
        )
        content = re.sub(r'extern struct OSThread_s \*(__osRunQueue);', linkage_fix, content)
        content = re.sub(r'extern struct OSThread_s \*(__osFaultedThread);', linkage_fix, content)

        # FINAL cast fix for exceptasm.cpp (now using raw array)
        content = re.sub(
            r'\(\s*\(\s*uint32_t\s*\*\s*\)\s*__osRunningThread->context\s*\)',
            '((uint32_t*)__osRunningThread->context)',
            content
        )
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        content = self.read_file(file_path)
        original_content = content

        if "n64_types.h" in file_path:
            # Aggressive purge
            content = re.sub(r'/\* OSTask/OSScTask forward decls.*?(?=#endif)#endif\n?', '', content, flags=re.DOTALL)
            content = re.sub(r'#ifndef OSTASK_FWD_DECLARED.*?(?=#endif)#endif\n?', '', content, flags=re.DOTALL)
            # ... (all previous purge lines unchanged)

            content = self._inject_primitives_block(content)
            content = self._inject_macros_block(content)          # ← NEW: early macros
            content = self._handle_exceptasm_fixes(content)

            # Force-inject all SDK opaque types at top
            for tag in self.SDK_DEFINES_THESE:
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content = f"struct {tag}_s {{ long long int force_align[64]; }};\ntypedef struct {tag}_s {tag};\n\n" + content

            # Apply struct bodies and globals (unchanged)
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

            for tag, body in self.PHASE_3_STRUCTS.items():
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

            for glob_var, decl in self.N64_KNOWN_GLOBALS.items():
                if not self._global_already_declared(glob_var, content):
                    wrapped_decl = f"""#ifdef __cplusplus
extern "C" {{
#endif
extern {decl}
#ifdef __cplusplus
}}
#endif
"""
                    content += f"\n#ifndef {glob_var}_DEFINED\n#define {glob_var}_DEFINED\n{wrapped_decl}\n#endif\n"

        if file_path.endswith(('.c', '.cpp')):
            content = self._handle_exceptasm_fixes(content)
            content = self._handle_float_initializers(content)

            # ... (POSIX and rule handling unchanged)

        if content != original_content:
            self.write_file(file_path, content)
            return 1
        return 0