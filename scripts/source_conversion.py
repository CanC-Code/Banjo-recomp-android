
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
        self.SDK_DEFINES_THESE = {"Actor", "OSScTask", "sChVegetable"}

        self.STANDARD_TYPES = {
            "uint8_t", "int8_t", "uint16_t", "int16_t", "uint32_t", "int32_t",
            "uint64_t", "int64_t", "size_t", "intptr_t", "uintptr_t", "ptrdiff_t",
            "bool", "_Bool", "wchar_t", "char16_t", "char32_t", "float", "double",
            "void", "char", "short", "int", "long", "unsigned", "signed",
            "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64", "n64_bool"
        }

        self.POSIX_RESERVED_NAMES = {
            "close", "open", "read", "write", "send", "recv", "connect", "accept",
            "bind", "listen", "select", "poll", "dup", "dup2", "fork", "exec", "exit",
            "stat", "fstat", "lstat", "access", "unlink", "rename", "mkdir", "rmdir",
            "chdir", "getcwd", "getpid", "getppid", "getuid", "getgid", "signal",
            "raise", "kill", "printf", "fprintf", "sprintf", "snprintf", "scanf",
            "fscanf", "sscanf", "time", "clock", "sleep", "usleep", "malloc", "calloc",
            "realloc", "free", "memcpy", "memset", "memmove", "memcmp", "strlen",
            "strcpy", "strncpy", "strcmp", "strncmp", "strcat", "strncat", "strchr",
            "strrchr", "strstr", "atoi", "atol", "atof", "strtol", "strtod", "abs",
            "labs", "fabs", "sqrt", "pow", "sin", "cos", "tan", "asin", "acos", "atan",
            "atan2", "rand", "srand",
        }

        self.N64_OS_OPAQUE_TYPES = {
            "OSPfs", "OSContStatus", "OSContPad", "OSPiHandle", "OSMesgQueue",
            "OSThread", "OSIoMesg", "OSTimer", "OSScTask", "OSTask", "OSScClient",
            "OSScKiller", "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr",
            "OSPfsState", "OSPfsFile", "OSPfsDir", "OSDevMgr", "SPTask", "GBIarg",
        }

        self.N64_AUDIO_STATE_TYPES = {
            "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "INTERLEAVE_STATE",
            "ENVMIX_STATE2", "HIPASSLOOP_STATE", "COMPRESS_STATE", "REVERB_STATE",
            "MIXER_STATE",
        }

        # ---------------------------------------------------------------------------
        # Macros & Struct Dicts
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
            "G_SHADE": "0x00000004", "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
        }

        self.N64_OS_STRUCT_BODIES = {
            "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { int16_t mi[4][4]; int16_t pad; } i; long long int force_align; } Mtx;",
            "OSContStatus": "typedef struct OSContStatus_s { uint16_t type; uint8_t status; uint8_t errno; } OSContStatus;",
            "OSContPad": "typedef struct OSContPad_s { uint16_t button; int8_t stick_x; int8_t stick_y; uint8_t errno; } OSContPad;",
            "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; int32_t validCount; int32_t first; int32_t msgCount; void *msg; } OSMesgQueue;",
            "OSThread": "typedef struct OSThread_s { struct OSThread_s *next; int32_t priority; struct OSThread_s **queue; struct OSThread_s *tlnext; uint16_t state; uint16_t flags; uint64_t id; int fp; long long int context[67]; } OSThread;",
            "OSMesgHdr": "typedef struct { uint16_t type; uint8_t pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
            "__OSBlockInfo": "typedef struct { uint32_t errStatus; void *dramAddr; void *C2Addr; uint32_t sectorSize; uint32_t C1ErrNum; uint32_t C1ErrSector[4]; } __OSBlockInfo;",
            "__OSTranxInfo": "typedef struct { uint32_t cmdType; uint16_t transferMode; uint16_t blockNum; int32_t sectorNum; uint32_t devAddr; uint32_t bmCtlShadow; uint32_t seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;",
            "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; __OSTranxInfo transferInfo; } OSPiHandle;",
            "OSIoMesg": "typedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; uint32_t devAddr; uint32_t size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
            "OSDevMgr": "typedef struct OSDevMgr_s { int32_t active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; } OSDevMgr;",
            "OSPfs": "typedef struct OSPfs_s { struct OSIoMesg_s ioMesgBuf; struct OSMesgQueue_s *queue; int32_t channel; uint8_t activebank; uint8_t banks; uint8_t inodeTable[256]; uint8_t dir[256]; uint32_t label[8]; int32_t repairList[256]; uint32_t version; uint32_t checksum; uint32_t inodeCacheIndex; uint8_t inodeCache[256]; } OSPfs;",
            "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; uint64_t interval; uint64_t value; struct OSMesgQueue_s *mq; void *msg; } OSTimer;",
            "LookAt": "typedef struct { struct { struct { float x, y, z; float pad; } l[2]; } l; } LookAt;",
            "ADPCM_STATE": "typedef struct { long long int force_align[16]; } ADPCM_STATE;",
            "Acmd": "typedef union { long long int force_align; uint32_t words[2]; } Acmd;",
            "Hilite": "typedef struct { int32_t words[2]; } Hilite;",
            "Light": "typedef struct { int32_t words[2]; } Light;",
            "uSprite": "typedef struct { long long int force_align[64]; } uSprite;",
            "CPUState": "typedef struct { long long int force_align[64]; } CPUState;",
            "OSTask": "typedef struct { uint32_t type; uint32_t flags; uint64_t *ucode_boot; uint32_t ucode_boot_size; uint64_t *ucode; uint32_t ucode_size; uint64_t *ucode_data; uint32_t ucode_data_size; uint64_t *dram_stack; uint32_t dram_stack_size; uint64_t *output_buff; uint64_t *output_buff_size; uint64_t *data_ptr; uint32_t data_size; uint64_t *yield_data_ptr; uint32_t yield_data_size; } OSTask_t; typedef union { OSTask_t t; long long int force_structure_alignment[64]; } OSTask;",
            "Vp": "typedef struct { short vscale[4]; short vtrans[4]; } Vp_t; typedef union { Vp_t vp; long long int force_align[8]; } Vp;"
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
            "osAppNMIBuffer": "uint32_t osAppNMIBuffer;",
            "osPiRawStartDma": "int32_t osPiRawStartDma(int32_t direction, uint32_t devAddr, void *dramAddr, uint32_t size);"
        }
        self.rules = []
        self.dynamic_categories = defaultdict(set)

    def _is_known_global(self, var_name: str) -> bool:
        return var_name in self.N64_KNOWN_GLOBALS

    def read_file(self, filepath: str) -> str:
        try:
            with open(filepath, 'r', errors='replace') as f:
                return f.read()
        except Exception:
            return ""

    def write_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, 'w') as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Failed to write {filepath}: {e}")

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
        if tag in self.SDK_DEFINES_THESE or tag in self.STANDARD_TYPES:
            return True
        if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content):
            return True
        if re.search(rf"\btypedef\s+(?:struct|union|enum)\s+{re.escape(tag)}\b", content):
            return True
        if f"{tag}_DEFINED" in content:
            return True
        return False

    def _global_already_declared(self, glob_var: str, content: str) -> bool:
        return bool(re.search(rf"\b{re.escape(glob_var)}\b", content))

    def strip_redefinition(self, content: str, tag: str) -> str:
        """Brace-matched removal of any struct/typedef definition for tag."""
        changed = True
        while changed:
            changed = False
            # Named struct body
            pattern1 = re.compile(rf"\bstruct\s+{re.escape(tag)}\s*\{{")
            match = pattern1.search(content)
            if match:
                start_idx = match.start()
                pre = content[:start_idx].rstrip()
                if pre.endswith("typedef"):
                    start_idx = pre.rfind("typedef")
                brace_idx = content.find('{', match.start())
                open_braces, curr_idx = 1, brace_idx + 1
                while curr_idx < len(content) and open_braces > 0:
                    if content[curr_idx] == '{': open_braces += 1
                    elif content[curr_idx] == '}': open_braces -= 1
                    curr_idx += 1
                semi_idx = content.find(';', curr_idx)
                if semi_idx != -1:
                    content = content[:start_idx] + f"/* AUTO-STRIPPED RE-DEF: {tag} */\n" + content[semi_idx+1:]
                    changed = True
                    continue

            # Anonymous typedef body ending in tag
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
        return content

    def repair_unterminated_conditionals(self, content: str) -> str:
        """Scan for #ifndef/#ifdef that are never closed and remove orphaned guards."""
        lines = content.split('\n')
        stack = []
        output = list(lines)
        remove = set()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'#\s*(?:ifndef|ifdef|if)\b', stripped):
                stack.append(i)
            elif re.match(r'#\s*endif\b', stripped):
                if stack:
                    stack.pop()

        for idx in stack:
            remove.add(idx)
            for j in range(idx + 1, min(idx + 4, len(lines))):
                if lines[j].strip().startswith('#define') or lines[j].strip().startswith('#endif'):
                    remove.add(j)
                    break

        if not remove: return content
        result = [line for i, line in enumerate(output) if i not in remove]
        return '\n'.join(result)

    def scrape_logs(self, log_content: str):
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", log_content):
            self.dynamic_categories["missing_types"].add(m.group(1))

        for m in re.finditer(r"error:\s+use of undeclared identifier '(\w+)'", log_content):
            self.dynamic_categories["undeclared_identifiers"].add(m.group(1))

        for m in re.finditer(r"error:\s+implicit declaration of function '(\w+)'", log_content):
            self.dynamic_categories["implicit_func_stubs"].add(m.group(1))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+initializing 'f32'", log_content):
            self.dynamic_categories["needs_float_fix"].add(m.group(1))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+(?:typedef )?redefinition", log_content):
            self.dynamic_categories["needs_redef_strip"].add(m.group(1))

        for m in re.finditer(r"error:\s+member reference (?:base )?type '.*?' is not a (?:pointer|structure or union)\n([^\n]+)\n", log_content):
            for mm in re.finditer(r'([A-Za-z0-9_]+)(?:->|\.)', m.group(1)):
                self.dynamic_categories["not_a_pointer"].add(mm.group(1))

        for m in re.finditer(r"error:\s+redefinition of '(\w+)' (?:with a different type|as different kind of symbol)", log_content):
            self.dynamic_categories["type_mismatches"].add(m.group(1))

        for m in re.finditer(r"error:\s+redefinition of '(\w+)' with a different type: '([^']+)'", log_content):
            var_name, var_type = m.group(1), m.group(2)
            var_type = re.sub(r"\s*\(aka '[^']+'\)", "", var_type)
            self.dynamic_categories["type_mismatches_resolved"].add((var_name, var_type))

        for m in re.finditer(r"(?m)^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+static declaration of '(\w+)' follows non-static", log_content):
            self.dynamic_categories["posix_reserved_conflict"].add((m.group(1), m.group(2)))

        for m in re.finditer(r"undefined reference to `(\w+)'", log_content):
            self.dynamic_categories["undefined_symbols"].add(m.group(1))

    def apply_dynamic_fixes(self):
        if not os.path.exists(self.types_header):
            return
        types_content = self.read_file(self.types_header)
        changed = False

        # Advanced Stub Generator
        for tag in self.dynamic_categories.get("missing_types", set()):
            if tag in self.SDK_DEFINES_THESE or tag in self.N64_OS_STRUCT_BODIES or tag in self.STANDARD_TYPES:
                continue
            if not self._type_already_defined(tag, types_content):
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
                wrapped_decl = f"""#ifdef __cplusplus
extern "C" {{
#endif
{decl}#ifdef __cplusplus
}}
#endif
"""
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{wrapped_decl}#endif\n"
                changed = True

        for ident in self.dynamic_categories.get("undeclared_identifiers", set()):
            if self._is_known_global(ident) or ident in self.PHASE_3_MACROS or ident in self.STANDARD_TYPES:
                continue
            if ident.isupper() or ident.startswith(("G_", "OS_", "PI_", "PFS_", "LEO_", "ADPCM")):
                decl = f"#define {ident} 0"
            else:
                decl = f"""#ifdef __cplusplus
extern "C" {{
#endif
extern long long int {ident};
#ifdef __cplusplus
}}
#endif
"""
            if decl not in types_content and f"{ident}_DEFINED" not in types_content:
                types_content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\n{decl}\n#endif\n"
                changed = True

        for member in self.dynamic_categories.get("not_a_pointer", set()):
            if isinstance(member, str):
                new_types, n = re.subn(
                    rf"\bextern\s+long\s+long\s+int\s+{re.escape(member)}\s*;",
                    f"extern void* {member}; /* AUTO-FIX: cast to pointer */", types_content)
                if n > 0:
                    types_content = new_types
                    changed = True

        # Resolve type mismatches actively (C++ friendly)
        for var_name, var_type in self.dynamic_categories.get("type_mismatches_resolved", set()):
            if self._is_known_global(var_name):
                continue  # GLOBAL PREEMPTION: Let the known globals handler manage this

            types_content = re.sub(
                rf'#ifndef {var_name}_DEFINED\n#define {var_name}_DEFINED\n(?:#ifdef __cplusplus\nextern "C" {{\n#endif\n)?extern long long int {var_name};\n(?:#ifdef __cplusplus\n}}\n#endif\n)?#endif\n?',
                '', types_content
            )
            decl = f"""#ifdef __cplusplus
extern "C" {{
#endif
extern {var_type} {var_name};
#ifdef __cplusplus
}}
#endif
"""
            if decl not in types_content:
                types_content += f"\n#ifndef {var_name}_DEFINED\n#define {var_name}_DEFINED\n{decl}\n#endif\n"
                changed = True

        for mismatch in self.dynamic_categories.get("type_mismatches", set()):
            if self._is_known_global(mismatch):
                continue  # GLOBAL PREEMPTION: Let the known globals handler manage this

            if not any(m == mismatch for m, _ in self.dynamic_categories.get("type_mismatches_resolved", set())):
                new_content, n = re.subn(
                    rf'#ifndef {mismatch}_DEFINED\n#define {mismatch}_DEFINED\n(?:#ifdef __cplusplus\nextern "C" {{\n#endif\n)?extern long long int {mismatch};\n(?:#ifdef __cplusplus\n}}\n#endif\n)?#endif\n?',
                    '', types_content
                )
                new_content, n2 = re.subn(
                    rf'(?:#ifdef __cplusplus\nextern "C" {{\n#endif\n)?extern long long int {mismatch};\n(?:#ifdef __cplusplus\n}}\n#endif\n)?\n?',
                    '', new_content
                )
                if n > 0 or n2 > 0:
                    types_content = new_content
                    changed = True

        # Undefined Symbols & Implicit functions -> n64_stubs.c
        stubs_added = False
        stubs_content = self.read_file(self.stubs_file) if os.path.exists(self.stubs_file) else '#include "n64_types.h"\n\n'
        for sym in self.dynamic_categories.get("undefined_symbols", set()) | self.dynamic_categories.get("implicit_func_stubs", set()):
            if isinstance(sym, str) and not sym.startswith("_Z") and "vtable" not in sym:
                if f" {sym}(" not in stubs_content:
                    stubs_content += f"long long int {sym}() {{ return 0; }}\n"
                    stubs_added = True

        if stubs_added:
            self.write_file(self.stubs_file, stubs_content)

        if changed:
            types_content = self.repair_unterminated_conditionals(types_content)
            self.write_file(self.types_header, types_content)

    def bootstrap_n64_types(self, clear_existing=False):
        os.makedirs(os.path.dirname(self.types_header), exist_ok=True)
        if clear_existing and os.path.exists(self.types_header):
            os.remove(self.types_header)
        if not os.path.exists(self.types_header):
            with open(self.types_header, 'w', encoding='utf-8') as f:
                f.write("#pragma once\n")
        if not os.path.exists(self.stubs_file):
            os.makedirs(os.path.dirname(self.stubs_file), exist_ok=True)
            with open(self.stubs_file, 'w', encoding='utf-8') as f:
                f.write('#include "n64_types.h"\n')

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

    def _handle_float_initializers(self, content: str) -> str:
        return re.sub(r'\{\s*NULL\s*,\s*NULL\s*\}', '{0.0f, 0.0f}', content)

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
        content = re.sub(
            r'__osRunningThread->context\.status',
            '((uint32_t*)__osRunningThread->context)[0]',
            content
        )
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        content = self.read_file(file_path)
        original_content = content

        if "n64_types.h" in file_path:
            # 1. AGGRESSIVE RUNNER CACHE PURGE
            content = re.sub(r'/\* OSTask/OSScTask forward decls.*?(?=#endif)#endif\n?', '', content, flags=re.DOTALL)
            content = re.sub(r'#ifndef OSTASK_FWD_DECLARED.*?(?=#endif)#endif\n?', '', content, flags=re.DOTALL)
            content = re.sub(r'typedef\s+struct\s+OSTask_s\s+OSTask;\n?', '', content)
            content = re.sub(r'struct\s+OSTask_s;\n?', '', content)
            content = re.sub(r'typedef\s+struct\s+OSScTask_s\s+OSScTask;\n?', '', content)
            content = re.sub(r'struct\s+OSScTask_s;\n?', '', content)
            content = re.sub(r'typedef\s+struct\s+sChVegetable_s\s+sChVegetable;\n?', '', content)
            content = re.sub(r'struct\s+sChVegetable_s;\n?', '', content)

            for prim in self.STANDARD_TYPES:
                content = re.sub(rf'typedef\s+struct\s+{prim}_s\s+{prim};\n?', '', content)
                content = re.sub(rf'struct\s+{prim}_s\s*\{{[^}}]*\}};\n?', '', content)

            # Purge globals carefully (accounting for the new extern "C" blocks and volatile qualifiers)
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

            # 2. Safely apply the standard body dict
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

            for tag, body in self.PHASE_3_STRUCTS.items():
                if not self._type_already_defined(tag, content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

            # Re-inject known globals with C++ safety
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

            # Advanced Local File POSIX Fixes
            for target_file, func_name in self.dynamic_categories.get("posix_reserved_conflict", set()):
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
