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
            "Mtx": """\
typedef union {
    struct { float mf[4][4]; } f;
    struct { int16_t mi[4][4]; int16_t pad; } i;
    long long int force_align;
} Mtx;""",
            "OSContStatus": "typedef struct OSContStatus_s { uint16_t type; uint8_t status; uint8_t errno; } OSContStatus;",
            "OSContPad": "typedef struct OSContPad_s { uint16_t button; int8_t stick_x; int8_t stick_y; uint8_t errno; } OSContPad;",
            "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; int32_t validCount; int32_t first; int32_t msgCount; void *msg; } OSMesgQueue;",
            "OSThread": "typedef struct OSThread_s { struct OSThread_s *next; int32_t priority; struct OSThread_s **queue; struct OSThread_s *tlnext; uint16_t state; uint16_t flags; uint64_t id; int fp; long long int context[67]; } OSThread;",
            "OSMesgHdr": "typedef struct { uint16_t type; uint8_t pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
            "OSPiHandle": """\
#ifndef __OSBlockInfo_DEFINED
#define __OSBlockInfo_DEFINED
typedef struct { uint32_t errStatus; void *dramAddr; void *C2Addr; uint32_t sectorSize; uint32_t C1ErrNum; uint32_t C1ErrSector[4]; } __OSBlockInfo;
#endif
#ifndef __OSTranxInfo_DEFINED
#define __OSTranxInfo_DEFINED
typedef struct { uint32_t cmdType; uint16_t transferMode; uint16_t blockNum; int32_t sectorNum; uint32_t devAddr; uint32_t bmCtlShadow; uint32_t seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;
#endif
typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; __OSTranxInfo transferInfo; } OSPiHandle;""",
            "OSIoMesg": "typedef struct OSIoMesg_s { void *hdr; void *dramAddr; uint32_t devAddr; uint32_t size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
            "OSDevMgr": "typedef struct OSDevMgr_s { int32_t active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; int32_t (*dma)(int32_t, uint32_t, void *, uint32_t); int32_t (*edma)(struct OSPiHandle_s *, int32_t, uint32_t, void *, uint32_t); } OSDevMgr;",
            "OSPfs": """\
typedef struct OSPfs_s {
    struct OSIoMesg_s    ioMesgBuf;
    struct OSMesgQueue_s *queue;
    int32_t         channel;
    uint8_t          activebank;
    uint8_t          banks;
    uint8_t          inodeTable[256];
    uint8_t          dir[256];
    uint32_t         label[8];
    int32_t         repairList[256];
    uint32_t         version;
    uint32_t         checksum;
    uint32_t         inodeCacheIndex;
    uint8_t          inodeCache[256];
} OSPfs;""",
            "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; uint64_t interval; uint64_t value; struct OSMesgQueue_s *mq; void *msg; } OSTimer;",
            "LookAt": "typedef struct { struct { struct { float x, y, z; float pad; } l[2]; } l; } LookAt;",
            "ADPCM_STATE": "typedef struct { long long int force_align[16]; } ADPCM_STATE;",
            "Acmd": "typedef union { long long int force_align; uint32_t words[2]; } Acmd;",
            "Hilite": "typedef struct { int32_t words[2]; } Hilite;",
            "Light": "typedef struct { int32_t words[2]; } Hilite;",
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
        self.N64_PRIMITIVES = {"u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"}
        self.N64_OS_OPAQUE_TYPES = {"OSPfs", "OSContStatus", "OSContPad", "OSPiHandle", "OSMesgQueue", "OSThread", "OSIoMesg", "OSTimer", "OSScTask", "OSTask", "OSScClient", "OSScKiller", "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr", "OSPfsState", "OSPfsFile", "OSPfsDir", "OSDevMgr", "SPTask", "GBIarg"}
        self.N64_AUDIO_STATE_TYPES = {"RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE", "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE"}
        self.POSIX_RESERVED_NAMES = {
            "close", "open", "read", "write", "send", "recv", "connect", "accept", "bind", "listen", "select", "poll", "dup", "dup2", "fork", "exec", "exit", "stat", "fstat", "lstat", "access", "unlink", "rename", "mkdir", "rmdir", "chdir", "getcwd", "getpid", "getppid", "getuid", "getgid", "signal", "raise", "kill", "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf", "time", "clock", "sleep", "usleep", "malloc", "calloc", "realloc", "free", "memcpy", "memset", "memmove", "memcmp", "strlen", "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strncat", "strchr", "strrchr", "strstr", "atoi", "atol", "atof", "strtol", "strtod", "abs", "labs", "fabs", "sqrt", "pow", "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "rand", "srand",
        }
        self.N64_KNOWN_GLOBALS = {
            "__osPiTable": "struct OSPiHandle_s *__osPiTable;",
            "__osFlashHandle": "struct OSPiHandle_s *__osFlashHandle;",
            "__osSfHandle": "struct OSPiHandle_s *__osSfHandle;",
            "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
            "__osRunQueue": "struct OSThread_s *__osRunQueue;",
            "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
        }
        self.SDK_DEFINES_THESE = {"OSTask", "OSScTask"}

    def read_file(self, filepath: str) -> str:
        try:
            with open(filepath, 'r', errors='replace') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return ""

    def write_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, 'w') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write {filepath}: {e}")

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

    def load_logic(self):
        self.rules = []
        pattern = os.path.join(self.logic_dir, "source_logic*.txt")
        found_files = glob.glob(pattern)
        for logic_file in found_files:
            with open(logic_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split(':::')
                        if len(parts) >= 4:
                            self.rules.append({
                                "action": parts[0], "name": parts[1],
                                "search": parts[2], "replace": parts[3].replace("\\n", "\n")
                            })

    def _type_already_defined(self, tag: str, content: str) -> bool:
        if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content):
            return True
        if re.search(rf"\btypedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content):
            return True
        if f"{tag}_DEFINED" in content:
            return True
        return False

    def _opaque_stub(self, tag: str, size: int = 64) -> str:
        struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
        return (
            f"#ifndef {tag}_DEFINED\n"
            f"#define {tag}_DEFINED\n"
            f"struct {struct_tag} {{ long long int force_align[{size}]; }};\n"
            f"typedef struct {struct_tag} {tag};\n"
            f"#endif\n"
        )

    def _inject_primitives_block(self, content: str) -> str:
        primitives_block = """\
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
typedef int32_t  OSIntMask;
typedef uint64_t OSTime;
typedef uint32_t OSId;
typedef int32_t  OSPri;
typedef void* OSMesg;
#endif
"""
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
        content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
        content = content.replace("#pragma once", f"#pragma once\n{primitives_block}", 1)
        return content

    def _inject_macros(self, content: str) -> str:
        for macro, value in self.PHASE_3_MACROS.items():
            if f"#define {macro}" not in content:
                content += f"\n#ifndef {macro}\n#define {macro} {value}\n#endif\n"
        return content

    def _inject_structs(self, content: str) -> str:
        for tag, body in {**self.N64_OS_STRUCT_BODIES, **self.PHASE_3_STRUCTS}.items():
            if not self._type_already_defined(tag, content):
                content += f"\n{body}\n"
        return content

    def _inject_globals(self, content: str) -> str:
        for glob, decl in self.N64_KNOWN_GLOBALS.items():
            if glob not in content:
                content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {decl}\n#endif\n"
        return content

    def _handle_opensl_es_headers(self, content: str) -> str:
        if '#include <SLES/OpenSLES.h>' not in content:
            content = f"#include <SLES/OpenSLES.h>\n#include <SLES/OpenSLES_Android.h>\n{content}"
        return content

    def _handle_pthread_header(self, content: str) -> str:
        if '#include <pthread.h>' not in content:
            content = f"#include <pthread.h>\n{content}"
        return content

    def _handle_jni_header(self, content: str) -> str:
        if '#include <jni.h>' not in content:
            content = f"#include <jni.h>\n{content}"
        return content

    def _handle_missing_macros(self, content: str) -> str:
        for macro in {"OEPRESCRIPT", "DANDROID02"}:
            if f"#define {macro}" not in content:
                content += f"\n#ifndef {macro}\n#define {macro} 1\n#endif\n"
        return content

    def _handle_stub_inject(self, sym: str) -> bool:
        if not sym or sym.startswith("_Z") or "vtable" in sym:
            return False
        stubs_content = ""
        if os.path.exists(self.stubs_file):
            with open(self.stubs_file, 'r', encoding='utf-8') as sf:
                stubs_content = sf.read()
        stub_func = f"void {sym}() {{}}\n"
        if stub_func not in stubs_content:
            with open(self.stubs_file, 'a', encoding='utf-8') as sf:
                sf.write(f"{stub_func}")
            return True
        return False

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
        if "sched_yield_DEFINED" not in content:
            content += f"\n{sched_yield_decl}\n"

        missing_functions = {
            "osCreateThread": "void osCreateThread(void* thread, void* func, void* arg) {}",
            "osDestroyThread": "void osDestroyThread(void* thread) {}",
            "sched_yield": "void sched_yield(void) {}",
        }
        stubs_content = ""
        if os.path.exists(self.stubs_file):
            with open(self.stubs_file, 'r', encoding='utf-8') as sf:
                stubs_content = sf.read()
        for func, stub in missing_functions.items():
            if stub not in stubs_content:
                with open(self.stubs_file, 'a', encoding='utf-8') as sf:
                    sf.write(f"{stub}\n")
        return content

    def _handle_math_conflicts(self, content: str) -> str:
        math_block = """
// Override math.h declarations to match PR/gu.h
#ifdef __cplusplus
extern "C" {
#endif
float cosf(float angle);
float sinf(float angle);
float sqrtf(float value);
#ifdef __cplusplus
}
#endif
"""
        if "float cosf(float angle);" not in content:
            if "#pragma once" in content:
                content = content.replace("#pragma once", f"#pragma once\n{math_block}", 1)
            else:
                content = math_block + content
        return content

    def _handle_exceptasm_fixes(self, content: str) -> str:
        # Wrap linkage overrides in __cplusplus guards to prevent C compiler errors
        content = re.sub(
            r'extern struct OSThread_s \*__osRunQueue;', 
            '#ifdef __cplusplus\\nextern "C" struct OSThread_s *__osRunQueue;\\n#else\\nextern struct OSThread_s *__osRunQueue;\\n#endif', 
            content
        )
        content = re.sub(
            r'extern struct OSThread_s \*__osFaultedThread;', 
            '#ifdef __cplusplus\\nextern "C" struct OSThread_s *__osFaultedThread;\\n#else\\nextern struct OSThread_s *__osFaultedThread;\\n#endif', 
            content
        )
        # Fix context.status access (only if it wasn't manually fixed in the source)
        content = re.sub(r'__osRunningThread->context\\.status', '((uint32_t*)__osRunningThread->context)[0]', content)
        return content

    def apply_to_file(self, file_path: str, error_context: str = "") -> int:
        if not os.path.exists(file_path):
            return 0
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        original_content = content
        changes = 0

        if "n64_types.h" in file_path:
            content = self._inject_primitives_block(content)
            content = self._handle_math_conflicts(content)
            content = self._inject_macros(content)
            content = self._inject_structs(content)
            content = self._inject_globals(content)
            content = self._handle_missing_macros(content)
            content = self._handle_missing_functions(content)
            content = self._handle_exceptasm_fixes(content)

        if "n64_types.h" not in file_path:
            content = self._handle_opensl_es_headers(content)
            content = self._handle_pthread_header(content)
            content = self._handle_jni_header(content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            changes += 1

        return changes
