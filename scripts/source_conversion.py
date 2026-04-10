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

        # ---------------------------------------------------------------------------
        # Core Protection Lists
        # ---------------------------------------------------------------------------
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

        self.POSIX_RESERVED_NAMES = {
            "close", "open", "read", "write", "send", "recv", "connect", "accept",
            "bind", "listen", "socket", "select", "poll", "fork", "exec", "wait",
            "kill", "signal", "alarm", "sleep", "usleep", "creat", "unlink", "stat",
            "fstat", "lstat", "chmod", "chown", "mkdir", "rmdir", "rename", "truncate"
        }

        # ---------------------------------------------------------------------------
        # Macros & Struct Dicts – FINAL VERSION
        # ---------------------------------------------------------------------------
        self.PHASE_3_MACROS = {
            "OS_IM_NONE": "0x0000", "OS_IM_1": "0x0001", "OS_IM_2": "0x0002", "OS_IM_3": "0x0004",
            "OS_IM_4": "0x0008", "OS_IM_5": "0x0010", "OS_IM_6": "0x0020", "OS_IM_7": "0x0040",
            "OS_IM_ALL": "0x007F", "PFS_ERR_ID_FATAL": "0x10", "PFS_ERR_DEVICE": "0x02",
            "PFS_ERR_CONTRFAIL": "0x01", "PFS_ERR_INVALID": "0x03", "PFS_ERR_EXIST": "0x04",
            "PFS_ERR_NOEXIST": "0x05", "PFS_DATA_ENXIO": "0x06",
            "ADPCMFSIZE": "9", "ADPCMVSIZE": "16",
            "UNITY_PITCH": "0x8000", "MAX_RATIO": "0xFFFF",
            "PI_DOMAIN1": "0", "PI_DOMAIN2": "1",
            "DEVICE_TYPE_64DD": "0x06",
            "LEO_CMD_TYPE_0": "0", "LEO_CMD_TYPE_1": "1", "LEO_CMD_TYPE_2": "2",
            "LEO_SECTOR_MODE": "1", "LEO_TRACK_MODE": "2",
            "LEO_BM_CTL": "0x05000510", "LEO_BM_CTL_RESET": "0", "LEO_ERROR_29": "29",
            "OS_READ": "0", "OS_WRITE": "1",
            "OS_MESG_NOBLOCK": "0", "OS_MESG_BLOCK": "1",
            "PI_STATUS_REG": "0x04600010", "PI_DRAM_ADDR_REG": "0x04600000",
            "PI_CART_ADDR_REG": "0x04600004", "PI_RD_LEN_REG": "0x04600008",
            "PI_WR_LEN_REG": "0x0460000C",
            "G_ON": "1", "G_OFF": "0",
            "G_ZBUFFER": "0x00000001", "G_SHADE": "0x00000004",
            "G_CULL_BACK": "0x00002000", "G_CULL_BOTH": "0x00003000",
            "G_FOG": "0x00010000", "G_LIGHTING": "0x00020000",
            "G_TEXTURE_GEN": "0x00040000", "G_TEXTURE_GEN_LINEAR": "0x00080000",
            "G_LOD": "0x00100000", "G_SHADING_SMOOTH": "0x00200000",
            "G_RM_AA_ZB_OPA_SURF": "0x00000000", "G_RM_AA_ZB_XLU_SURF": "0x00000000",
            "G_CC_SHADE": "0x00000000",
            "OS_CLOCK_RATE": "62500000LL",
            "OS_APP_NMI_BUFSIZE": "64",
        }

        self.N64_OS_STRUCT_BODIES = {
            "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { int16_t mi[4][4]; int16_t pad; } i; long long int force_align; } Mtx;",
            "OSContStatus": "typedef struct OSContStatus_s { uint16_t type; uint8_t status; uint8_t errno; } OSContStatus;",
            "OSContPad": "typedef struct OSContPad_s { uint16_t button; int8_t stick_x; int8_t stick_y; uint8_t errno; } OSContPad;",
            "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; int32_t validCount; int32_t first; int32_t msgCount; OSMesg *msg; } OSMesgQueue;",

            # CRITICAL: Named inner struct + union for dual compatibility
            "OSThread": """typedef union __OSThreadContext_u {
    struct {
        uint64_t pc;
        uint64_t a0;
        uint64_t sp;
        uint64_t ra;
        uint32_t sr;
        uint32_t rcp;
        uint32_t fpcsr;
    } regs;
    long long int force_align[67];
} __OSThreadContext;
typedef struct OSThread_s {
    struct OSThread_s *next;
    int32_t priority;
    struct OSThread_s **queue;
    struct OSThread_s *tlnext;
    uint16_t state;
    uint16_t flags;
    uint64_t id;
    int fp;
    __OSThreadContext context;
} OSThread;""",

            "OSMesgHdr": "typedef struct { uint16_t type; uint8_t pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
            "__OSBlockInfo": "typedef struct { uint32_t errStatus; void *dramAddr; void *C2Addr; uint32_t sectorSize; uint32_t C1ErrNum; uint32_t C1ErrSector[4]; } __OSBlockInfo;",
            "__OSTranxInfo": "typedef struct { uint32_t cmdType; uint16_t transferMode; uint16_t blockNum; int32_t sectorNum; uint32_t devAddr; uint32_t bmCtlShadow; uint32_t seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;",
            "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; __OSTranxInfo transferInfo; } OSPiHandle;",
            "OSIoMesg": "typedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; uint32_t devAddr; uint32_t size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
            "OSDevMgr": """typedef struct OSDevMgr_s {
    int32_t active;
    struct OSThread_s *thread;
    struct OSMesgQueue_s *cmdQueue;
    struct OSMesgQueue_s *evtQueue;
    struct OSMesgQueue_s *acsQueue;
    int32_t (*dma)(int32_t, void*, void*, uint32_t);
    int32_t (*edma)(struct OSPiHandle_s*, int32_t, void*, void*, uint32_t);
} OSDevMgr;""",
            "OSPfs": "typedef struct OSPfs_s { struct OSIoMesg_s ioMesgBuf; struct OSMesgQueue_s *queue; int32_t channel; uint8_t activebank; uint8_t banks; uint8_t inodeTable[256]; uint8_t dir[256]; uint32_t label[8]; int32_t repairList[256]; uint32_t version; uint32_t checksum; uint32_t inodeCacheIndex; uint8_t inodeCache[256]; } OSPfs;",
            "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; uint64_t interval; uint64_t value; struct OSMesgQueue_s *mq; void *msg; } OSTimer;",
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

    # -----------------------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------------------
    def read_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""

    def write_file(self, file_path: str, content: str):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def _type_already_defined(self, tag: str, content: str) -> bool:
        patterns = [
            rf'typedef .*?\b{tag}\b',
            rf'struct .*?\b{tag}\b',
            rf'#define .*?\b{tag}\b'
        ]
        return any(re.search(p, content) for p in patterns)

    def _global_already_declared(self, glob_var: str, content: str) -> bool:
        return bool(re.search(rf'\b{glob_var}\b', content))

    def strip_redefinition(self, content: str, tag: str) -> str:
        # Aggressive removal of duplicate typedef/struct
        content = re.sub(rf'typedef\s+struct\s+{tag}_s\s*{{[^}}]*}}\s*{tag};?', '', content)
        content = re.sub(rf'struct\s+{tag}_s\s*{{[^}}]*}};', '', content)
        content = re.sub(rf'typedef\s+struct\s+{tag}\s+{tag};?', '', content)
        return content

    def _inject_primitives_block(self, content: str) -> str:
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
        if "n64_bool" not in content:
            content += '\n#ifndef n64_bool\n#define n64_bool int\n#endif\n'
        return content

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

        # Force correct cast for exceptasm.cpp
        content = re.sub(
            r'\(\s*\(\s*uint32_t\s*\*\s*\)\s*__osRunningThread->context\s*\)',
            '((uint32_t*)&__osRunningThread->context.force_align[0])',
            content
        )
        # Force createthread.c member access through the named inner struct
        content = re.sub(r'->context\.([a-z0-9_]+)', r'->context.regs.\1', content)
        return content

    def _handle_float_initializers(self, content: str) -> str:
        content = re.sub(r'\{\s*NULL\s*,\s*NULL\s*\}', '{0.0f, 0.0f}', content)
        content = re.sub(r'\{\s*NULL\s*,\s*NULL\s*,\s*NULL\s*,\s*NULL\s*\}', '{NULL, 0, 0.0f}', content)
        return content

    def load_logic(self):
        """Placeholder – loads rules from logic_dir if files exist (can be extended later)"""
        self.rules = []  # No external rules yet – all fixes are inline
        logger.info("Logic loaded (inline rules active)")

    def scrape_logs(self, log_content: str):
        """Populate dynamic_categories from build log"""
        self.dynamic_categories = defaultdict(set)

        # Unknown types
        for m in re.finditer(r"unknown type name ['\"](.*?)['\"]", log_content):
            typ = m.group(1).strip()
            if typ not in self.STANDARD_TYPES and typ not in self.SDK_DEFINES_THESE:
                self.dynamic_categories["missing_types"].add(typ)

        # Undeclared identifiers
        for m in re.finditer(r"use of undeclared identifier ['\"](.*?)['\"]", log_content):
            ident = m.group(1).strip()
            self.dynamic_categories["undeclared_identifiers"].add(ident)

        # Redefinitions
        for m in re.finditer(r"redefinition of ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["needs_redef_strip"].add(m.group(1).strip())

        # Float / initializer issues
        if "initializer element is not a compile-time constant" in log_content or "float" in log_content.lower():
            self.dynamic_categories["needs_float_fix"].add("particle.c")  # extend as needed

        # POSIX static conflicts
        for m in re.finditer(r"static declaration of ['\"](.*?)['\"] follows non-static", log_content):
            func = m.group(1).strip()
            if func in self.POSIX_RESERVED_NAMES:
                self.dynamic_categories["posix_reserved_conflict"].add((os.path.basename(log_content.split(":")[0] if ":" in log_content else ""), func))

        logger.info(f"Scraped {sum(len(v) for v in self.dynamic_categories.values())} dynamic issues")

    def apply_dynamic_fixes(self):
        """Apply scraped fixes to types_header and stubs"""
        if not os.path.exists(self.types_header):
            return

        with open(self.types_header, 'a', encoding='utf-8') as f:
            for typ in self.dynamic_categories.get("missing_types", set()):
                if typ not in self.N64_OS_STRUCT_BODIES:
                    f.write(f"\n/* Dynamic opaque: */ typedef struct {typ}_s {typ};\n")

        logger.info("Dynamic fixes applied to types/stubs")

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        content = self.read_file(file_path)
        original_content = content

        if "n64_types.h" in file_path:
            # Aggressive purge of stale forward declarations
            content = re.sub(r'/\* OSTask/OSScTask forward decls.*?(?=#endif)#endif\n?', '', content, flags=re.DOTALL)
            content = re.sub(r'#ifndef OSTASK_FWD_DECLARED.*?(?=#endif)#endif\n?', '', content, flags=re.DOTALL)
            content = re.sub(r'typedef\s+struct\s+(?:OSTask|OSScTask|sChVegetable|LetterFloorTile|MapProgressFlagToDialogID)_s\s+.*?;?\n?', '', content)
            content = re.sub(r'struct\s+(?:OSTask|OSScTask|sChVegetable|LetterFloorTile|MapProgressFlagToDialogID)_s;\n?', '', content)

            for prim in self.STANDARD_TYPES:
                content = re.sub(rf'typedef\s+struct\s+{prim}_s\s+{prim};\n?', '', content)
                content = re.sub(rf'struct\s+{prim}_s\s*\{{[^}}]*\}};\n?', '', content)

            # Purge old globals
            for glob_var in self.N64_KNOWN_GLOBALS:
                content = re.sub(
                    rf'#ifndef {glob_var}_DEFINED\n#define {glob_var}_DEFINED\n(?:#ifdef __cplusplus\nextern "C" {{\n#endif\n)?extern [^\n]*\b{glob_var}\b[^\n]*;\n(?:#ifdef __cplusplus\n}}\n#endif\n)?#endif\n?',
                    '', content
                )
                content = re.sub(
                    rf'(?:#ifdef __cplusplus\nextern "C" {{\n#endif\n)?extern [^\n]*\b{glob_var}\b[^\n]*;\n(?:#ifdef __cplusplus\n}}\n#endif\n)?\n?',
                    '', content
                )

            content = self._inject_primitives_block(content)
            content = self._handle_exceptasm_fixes(content)

            # Inject all our structs
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

            for tag, body in self.PHASE_3_STRUCTS.items():
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

            # Inject globals
            for glob_var, decl in self.N64_KNOWN_GLOBALS.items():
                if not self._global_already_declared(glob_var, content):
                    wrapped = f"""#ifdef __cplusplus
extern "C" {{
#endif
extern {decl}
#ifdef __cplusplus
}}
#endif
"""
                    content += f"\n#ifndef {glob_var}_DEFINED\n#define {glob_var}_DEFINED\n{wrapped}\n#endif\n"

        if file_path.endswith(('.c', '.cpp')):
            content = self._handle_exceptasm_fixes(content)
            content = self._handle_float_initializers(content)

            # POSIX static renames
            for target_file, func_name in list(self.dynamic_categories.get("posix_reserved_conflict", set())):
                if func_name in self.POSIX_RESERVED_NAMES and (file_path.endswith(target_file) or target_file.endswith(file_path)):
                    prefix = os.path.basename(file_path).split('.')[0]
                    new_name = f"n64_{prefix}_{func_name}"
                    define = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
                    if define not in content:
                        includes = list(re.finditer(r'#include\s+.*?\n', content))
                        idx = includes[-1].end() if includes else 0
                        content = content[:idx] + define + content[idx:]

            for rule in self.rules:
                if rule['action'] == 'replace':
                    content = content.replace(rule['search'], rule['replace'])
                elif rule['action'] == 'regex':
                    content = re.sub(rule['search'], rule['replace'], content)

        if content != original_content:
            self.write_file(file_path, content)
            return 1
        return 0