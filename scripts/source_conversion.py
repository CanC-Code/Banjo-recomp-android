
import os
import re
import glob
from collections import defaultdict

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.rules = []
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"
        self.intelligence_level = 1
        self.PHASE_1_MACROS = {
            "OS_IM_NONE": "0x0000", "OS_IM_1": "0x0001", "OS_IM_2": "0x0002", "OS_IM_3": "0x0004",
            "OS_IM_4": "0x0008", "OS_IM_5": "0x0010", "OS_IM_6": "0x0020", "OS_IM_7": "0x0040",
            "OS_IM_ALL": "0x007F", "PFS_ERR_ID_FATAL": "0x10", "PFS_ERR_DEVICE": "0x02",
            "PFS_ERR_CONTRFAIL": "0x01", "PFS_ERR_INVALID": "0x03", "PFS_ERR_EXIST": "0x04",
            "PFS_ERR_NOEXIST": "0x05", "PFS_DATA_ENXIO": "0x06", "ADPCMFSIZE": "9",
            "ADPCMVSIZE": "16", "UNITY_PITCH": "0x8000", "MAX_RATIO": "0xFFFF",
            "PI_DOMAIN1": "0", "PI_DOMAIN2": "1",
        }
        self.PHASE_2_MACROS = {**self.PHASE_1_MACROS, **{
            "DEVICE_TYPE_64DD": "0x06", "LEO_CMD_TYPE_0": "0", "LEO_CMD_TYPE_1": "1",
            "LEO_CMD_TYPE_2": "2", "LEO_SECTOR_MODE": "1", "LEO_TRACK_MODE": "2",
            "LEO_BM_CTL": "0x05000510", "LEO_BM_CTL_RESET": "0", "LEO_ERROR_29": "29",
            "OS_READ": "0", "OS_WRITE": "1", "OS_MESG_NOBLOCK": "0", "OS_MESG_BLOCK": "1",
            "PI_STATUS_REG": "0x04600010", "PI_DRAM_ADDR_REG": "0x04600000",
            "PI_CART_ADDR_REG": "0x04600004", "PI_RD_LEN_REG": "0x04600008",
            "PI_WR_LEN_REG": "0x0460000C", "PI_STATUS_DMA_BUSY": "0x01",
            "PI_STATUS_IO_BUSY": "0x02", "PI_STATUS_ERROR": "0x04",
            "PI_STATUS_INTERRUPT": "0x08", "PI_BSD_DOM1_LAT_REG": "0x04600014",
            "PI_BSD_DOM1_PWD_REG": "0x04600018", "PI_BSD_DOM1_PGS_REG": "0x0460001C",
            "PI_BSD_DOM1_RLS_REG": "0x04600020", "PI_BSD_DOM2_LAT_REG": "0x04600024",
            "PI_BSD_DOM2_PWD_REG": "0x04600028", "PI_BSD_DOM2_PGS_REG": "0x0460002C",
            "PI_BSD_DOM2_RLS_REG": "0x04600030",
        }}
        self.PHASE_3_MACROS = {**self.PHASE_2_MACROS, **{
            "G_ON": "1", "G_OFF": "0", "G_RM_AA_ZB_OPA_SURF": "0x00000000",
            "G_RM_AA_ZB_OPA_SURF2": "0x00000000", "G_RM_AA_ZB_XLU_SURF": "0x00000000",
            "G_RM_AA_ZB_XLU_SURF2": "0x00000000", "G_ZBUFFER": "0x00000001",
            "G_SHADE": "0x00000004", "G_CULL_BACK": "0x00002000", "G_CC_SHADE": "0x00000000",
        }}
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

    def repair_unterminated_conditionals(self, content: str) -> str:
        lines = content.split('\n')
        stack = []
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
                if lines[j].strip().startswith('#define'):
                    remove.add(j)
                    break
        if not remove:
            return content
        return '\n'.join([line for i, line in enumerate(lines) if i not in remove])

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

    def _strip_redefinition(self, content: str, tag: str) -> str:
        changed = True
        while changed:
            changed = False
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
                    if content[curr_idx] == '{':
                        open_braces += 1
                    elif content[curr_idx] == '}':
                        open_braces -= 1
                    curr_idx += 1
                semi_idx = content.find(';', curr_idx)
                if semi_idx != -1:
                    content = content[:start_idx] + f"/* AUTO-STRIPPED RE-DEF: {tag} */\n" + content[semi_idx+1:]
                    changed = True
                    continue
            idx = 0
            while True:
                match = re.search(r"\btypedef\s+struct\b[^{]*\{", content[idx:])
                if not match:
                    break
                start_idx = idx + match.start()
                brace_idx = content.find('{', start_idx)
                open_braces, curr_idx = 1, brace_idx + 1
                while curr_idx < len(content) and open_braces > 0:
                    if content[curr_idx] == '{':
                        open_braces += 1
                    elif content[curr_idx] == '}':
                        open_braces -= 1
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
            if changed:
                continue
            c_new, n = re.subn(rf"\btypedef\s+(?:struct\s+)?[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;", f"/* STRIPPED LOOSE TYPEDEF: {tag} */", content)
            if n > 0:
                content, changed = c_new, True
            c_new, n = re.subn(rf"\bstruct\s+{re.escape(tag)}\s*;", f"/* STRIPPED FWD DECL: {tag} */", content)
            if n > 0:
                content, changed = c_new, True
        return content

    def _rename_posix_static(self, content: str, func_name: str, filepath: str) -> Tuple[str, bool]:
        prefix = os.path.basename(filepath).split('.')[0]
        new_name = f"n64_{prefix}_{func_name}"
        define = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
        if define in content:
            return content, False
        includes = list(re.finditer(r'#include\s+.*?\n', content))
        idx = includes[-1].end() if includes else 0
        return content[:idx] + define + content[idx:], True

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
typedef void*    OSMesg;
#endif
"""
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
        content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
        content = content.replace("#pragma once", f"#pragma once\n{primitives_block}", 1)
        return content

    def _inject_macros(self, content: str, macros: Dict[str, str]) -> str:
        for macro, value in macros.items():
            if f"#define {macro}" not in content:
                content += f"\n#ifndef {macro}\n#define {macro} {value}\n#endif\n"
        return content

    def _inject_structs(self, content: str, structs: Dict[str, str]) -> str:
        for tag, body in structs.items():
            if not self._type_already_defined(tag, content):
                content += f"\n{body}\n"
        return content

    def _inject_globals(self, content: str) -> str:
        for glob, decl in self.N64_KNOWN_GLOBALS.items():
            if glob not in content:
                content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {decl}\n#endif\n"
        return content

    def _handle_missing_types(self, content: str, error_context: str) -> str:
        missing_types = set()
        for m in re.finditer(r"unknown type name '(\w+)'", error_context):
            missing_types.add(m.group(1))
        for tag in missing_types:
            if tag in self.N64_PRIMITIVES:
                continue
            elif tag in self.N64_OS_STRUCT_BODIES:
                if not self._type_already_defined(tag, content):
                    content += f"\n{self.N64_OS_STRUCT_BODIES[tag]}\n"
            elif tag in self.N64_OS_OPAQUE_TYPES:
                if not self._type_already_defined(tag, content):
                    content += f"\n{self._opaque_stub(tag)}\n"
            elif tag in self.N64_AUDIO_STATE_TYPES:
                if not self._type_already_defined(tag, content):
                    content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
            else:
                if not self._type_already_defined(tag, content):
                    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                    content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\nstruct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n#endif\n"
        return content

    def _handle_posix_conflicts(self, content: str, error_context: str, filepath: str) -> str:
        for m in re.finditer(r"static declaration of '(\w+)' follows non-static declaration", error_context):
            func_name = m.group(1)
            if func_name in self.POSIX_RESERVED_NAMES:
                content, _ = self._rename_posix_static(content, func_name, filepath)
        return content

    def _handle_undeclared_identifiers(self, content: str, error_context: str) -> str:
        undeclared_idents = set()
        for m in re.finditer(r"use of undeclared identifier '(\w+)'", error_context):
            undeclared_idents.add(m.group(1))
        for ident in undeclared_idents:
            if ident in self.N64_KNOWN_GLOBALS:
                continue
            if ident in self.PHASE_3_MACROS:
                if f"#define {ident}" not in content:
                    content += f"\n#ifndef {ident}\n#define {ident} {self.PHASE_3_MACROS[ident]}\n#endif\n"
            elif ident.isupper() or ident.startswith(("G_", "OS_", "PI_", "PFS_", "LEO_", "ADPCM", "UNITY", "MAX_")):
                if f"#define {ident}" not in content:
                    content += f"\n#ifndef {ident}\n#define {ident} 0 /* AUTO-INJECTED UNDECLARED IDENTIFIER */\n#endif\n"
            else:
                if f"extern long long int {ident};" not in content:
                    content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\nextern long long int {ident};\n#endif\n"
        return content

    def _handle_implicit_functions(self, content: str, error_context: str) -> str:
        implicit_funcs = set()
        for m in re.finditer(r"implicit declaration of function '(\w+)'", error_context):
            implicit_funcs.add(m.group(1))
        for func in implicit_funcs:
            if func in {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round", "memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp", "malloc", "free", "exit", "atoi", "rand", "srand"}:
                continue
            if f"extern long long int {func}();" not in content:
                content += f"\n#ifndef {func}_DEFINED\n#define {func}_DEFINED\nextern long long int {func}();\n#endif\n"
        return content

    def _handle_opensl_es_headers(self, content: str, error_context: str) -> str:
        if re.search(r"unknown type name '(?:SLEngineItf|SLObjectItf|SLPlayItf|SLVolumeItf|SLAndroidSimpleBufferQueueItf)'", error_context):
            if '#include <SLES/OpenSLES.h>' not in content:
                content = f"#include <SLES/OpenSLES.h>\n#include <SLES/OpenSLES_Android.h>\n{content}"
        return content

    def _handle_pthread_header(self, content: str, error_context: str) -> str:
        if re.search(r"'pthread_t' was not declared in this scope", error_context):
            if '#include <pthread.h>' not in content:
                content = f"#include <pthread.h>\n{content}"
        return content

    def _handle_jni_header(self, content: str, error_context: str) -> str:
        if re.search(r"'JNIEnv' was not declared in this scope", error_context):
            if '#include <jni.h>' not in content:
                content = f"#include <jni.h>\n{content}"
        return content

    def _handle_missing_macros(self, content: str, error_context: str) -> str:
        missing_macros = set()
        for m in re.finditer(r"'([A-Za-z0-9_]+)' was not declared in this scope", error_context):
            missing_macros.add(m.group(1))
        for macro in missing_macros:
            if macro in {"OEPRESCRIPT", "DANDROID02"}:
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
        stub_func = f"long long int {sym}() {{ return 0; }}"
        if stub_func not in stubs_content:
            with open(self.stubs_file, 'a', encoding='utf-8') as sf:
                sf.write(f"{stub_func}\n")
            return True
        return False

    def apply_to_file(self, file_path: str, error_context: str = "") -> int:
        if not os.path.exists(file_path):
            return 0
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        original_content = content
        changes = 0

        # Apply logic rules
        for rule in self.rules:
            try:
                if rule["action"] == "REGEX":
                    new_content, count = re.subn(rule["search"], rule["replace"], content)
                    if count > 0:
                        content, changes = new_content, changes + count
                elif rule["action"] == "HEADER_INJECT":
                    if re.search(rule["search"], error_context) and rule["replace"] not in content:
                        content, changes = f"{rule['replace']}\n{content}", changes + 1
                elif rule["action"] == "GLOBAL_INJECT":
                    if "n64_types.h" in file_path and re.search(rule["search"], error_context):
                        rule_marker = f"/* Rule: {rule['name']} */"
                        if rule_marker not in content:
                            new_header_data = f"{content}\n{rule_marker}\n{rule['replace']}\n"
                            content = self.repair_unterminated_conditionals(new_header_data)
                            changes += 1
                elif rule["action"] == "STUB_INJECT":
                    match = re.search(rule["search"], error_context)
                    if match and self._handle_stub_inject(match.group(1)):
                        changes += 1
            except re.error:
                continue

        # Apply progressive fixes if this is n64_types.h
        if "n64_types.h" in file_path:
            content = self._inject_primitives_block(content)
            if self.intelligence_level >= 1:
                content = self._inject_macros(content, self.PHASE_1_MACROS)
            if self.intelligence_level >= 2:
                content = self._inject_macros(content, self.PHASE_2_MACROS)
                content = self._inject_structs(content, self.N64_OS_STRUCT_BODIES)
            if self.intelligence_level >= 3:
                content = self._inject_macros(content, self.PHASE_3_MACROS)
            content = self._inject_globals(content)
            content = self._handle_missing_types(content, error_context)
            content = self._handle_undeclared_identifiers(content, error_context)
            content = self._handle_implicit_functions(content, error_context)
            content = self.repair_unterminated_conditionals(content)

        # Handle OpenSL ES, POSIX, JNI, and missing macros in source files
        if "n64_types.h" not in file_path:
            content = self._handle_opensl_es_headers(content, error_context)
            content = self._handle_pthread_header(content, error_context)
            content = self._handle_jni_header(content, error_context)
            content = self._handle_missing_macros(content, error_context)
            content = self._handle_posix_conflicts(content, error_context, file_path)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        return changes

    def escalate_intelligence(self):
        self.intelligence_level = min(self.intelligence_level + 1, 3)
