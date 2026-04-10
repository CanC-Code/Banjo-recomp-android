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
        
        # Types that the game natively defines. Auto-scraper MUST NOT stub these.
        self.SDK_DEFINES_THESE = {"OSTask", "OSScTask", "Actor"}

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
            "uSprite": "typedef struct { long long int force_align[64]; } uSprite;",
            "CPUState": "typedef struct { long long int force_align[64]; } CPUState;",
            "sChVegetable": "typedef struct sChVegetable_s sChVegetable;"
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
        self.rules = []
        self.dynamic_categories = defaultdict(set)

    def read_file(self, filepath: str) -> str:
        try:
            with open(filepath, 'r', errors='replace') as f: return f.read()
        except Exception: return ""

    def write_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, 'w') as f: f.write(content)
        except Exception as e: logger.error(f"Failed to write {filepath}: {e}")

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
        if tag in self.SDK_DEFINES_THESE: return True
        if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content): return True
        if re.search(rf"\btypedef\s+(?:struct|union|enum)\s+{re.escape(tag)}\b", content): return True
        if f"{tag}_DEFINED" in content: return True
        return False

    def strip_redefinition(self, content: str, tag: str) -> str:
        changed = True
        while changed:
            changed = False
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
        return content

    def scrape_logs(self, log_content: str):
        """Self-healing engine component: Scrapes build logs to dynamically discover missing types."""
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", log_content):
            self.dynamic_categories["missing_types"].add(m.group(1))
        
        for m in re.finditer(r"error:\s+use of undeclared identifier '(\w+)'", log_content):
            self.dynamic_categories["undeclared_identifiers"].add(m.group(1))
            
        for m in re.finditer(r"error:\s+implicit declaration of function '(\w+)'", log_content):
            self.dynamic_categories["implicit_func_stubs"].add(m.group(1))

    def apply_dynamic_fixes(self):
        """Self-healing engine component: Injects scraped types into headers dynamically."""
        if not os.path.exists(self.types_header): return
        types_content = self.read_file(self.types_header)
        changed = False

        for tag in self.dynamic_categories.get("missing_types", set()):
            if tag in self.SDK_DEFINES_THESE or tag in self.N64_OS_STRUCT_BODIES:
                continue
            if not self._type_already_defined(tag, types_content):
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                changed = True

        for ident in self.dynamic_categories.get("undeclared_identifiers", set()):
            if ident in self.N64_KNOWN_GLOBALS or ident in self.PHASE_3_MACROS:
                continue
            decl = f"extern long long int {ident};"
            if decl not in types_content and f"{ident}_DEFINED" not in types_content:
                types_content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\n{decl}\n#endif\n"
                changed = True

        if changed:
            self.write_file(self.types_header, types_content)

    def bootstrap_n64_types(self, clear_existing=False):
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
        if clear_existing and os.path.exists(self.types_header): os.remove(self.types_header)
        if not os.path.exists(self.types_header):
            with open(self.types_header, 'w', encoding='utf-8') as f: f.write("#pragma once\n")
        if not os.path.exists(self.stubs_file):
            os.makedirs(os.path.dirname(self.stubs_file), exist_ok=True)
            with open(self.stubs_file, 'w', encoding='utf-8') as f: f.write('#include "n64_types.h"\n')

    def _inject_primitives_block(self, content: str) -> str:
        # Enforce C standard linkage for math before N64 headers are loaded to prevent NDK 25 C++ clashes.
        primitives_block = """\
#include <stdint.h>
#include <sched.h>

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
#ifdef __cplusplus
}
#endif

#endif
"""
        if "#pragma once" not in content: content = "#pragma once\n" + content
        content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
        return content.replace("#pragma once", f"#pragma once\n{primitives_block}", 1)

    def _handle_float_initializers(self, content: str) -> str:
        return re.sub(r'\{\s*NULL\s*,\s*NULL\s*\}', '{0.0f, 0.0f}', content)

    def _handle_exceptasm_fixes(self, content: str) -> str:
        linkage_fix = r'#ifdef __cplusplus\nextern "C" struct OSThread_s *\1;\n#else\nextern struct OSThread_s *\1;\n#endif'
        content = re.sub(r'extern struct OSThread_s \*(__osRunQueue);', linkage_fix, content)
        content = re.sub(r'extern struct OSThread_s \*(__osFaultedThread);', linkage_fix, content)
        content = re.sub(r'__osRunningThread->context\.status', '((uint32_t*)__osRunningThread->context)[0]', content)
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path): return 0
        content = self.read_file(file_path)
        original_content = content

        if "n64_types.h" in file_path:
            content = self._inject_primitives_block(content)
            content = self._handle_exceptasm_fixes(content)
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if not self._type_already_defined(tag, content): 
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"
            for tag, body in self.PHASE_3_STRUCTS.items():
                if not self._type_already_defined(tag, content): 
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"
            for glob_var, decl in self.N64_KNOWN_GLOBALS.items():
                if glob_var not in content: content += f"\nextern {decl}\n"

        if file_path.endswith(('.c', '.cpp')):
            content = self._handle_exceptasm_fixes(content)
            content = self._handle_float_initializers(content)
            
            for rule in self.rules:
                if rule['action'] == 'replace':
                    content = content.replace(rule['search'], rule['replace'])
                elif rule['action'] == 'regex':
                    content = re.sub(rule['search'], rule['replace'], content)

        if content != original_content:
            self.write_file(file_path, content)
            return 1
        return 0
