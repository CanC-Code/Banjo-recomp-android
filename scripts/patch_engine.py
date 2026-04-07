import os
import re
import logging
import sys
import yaml
import networkx as nx
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional, Union, Callable
from dataclasses import dataclass

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")
logger.setLevel(logging.INFO)

# --- Paths ---
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# --- Data Classes ---
@dataclass
class ErrorFix:
    regex: str
    category: str
    handler: Callable
    priority: int = 1

# --- Config Data (Embedded YAML) ---
PHASE_1_MACROS = """
OS_IM_NONE: "0x0000"
OS_IM_1: "0x0001"
OS_IM_2: "0x0002"
OS_IM_3: "0x0004"
OS_IM_4: "0x0008"
OS_IM_5: "0x0010"
OS_IM_6: "0x0020"
OS_IM_7: "0x0040"
OS_IM_ALL: "0x007F"
PFS_ERR_ID_FATAL: "0x10"
PFS_ERR_DEVICE: "0x02"
PFS_ERR_CONTRFAIL: "0x01"
PFS_ERR_INVALID: "0x03"
PFS_ERR_EXIST: "0x04"
PFS_ERR_NOEXIST: "0x05"
PFS_DATA_ENXIO: "0x06"
ADPCMFSIZE: "9"
ADPCMVSIZE: "16"
UNITY_PITCH: "0x8000"
MAX_RATIO: "0xFFFF"
PI_DOMAIN1: "0"
PI_DOMAIN2: "1"
"""

PHASE_2_MACROS = """
DEVICE_TYPE_64DD: "0x06"
LEO_CMD_TYPE_0: "0"
LEO_CMD_TYPE_1: "1"
LEO_CMD_TYPE_2: "2"
LEO_SECTOR_MODE: "1"
LEO_TRACK_MODE: "2"
LEO_BM_CTL: "0x05000510"
LEO_BM_CTL_RESET: "0"
LEO_ERROR_29: "29"
OS_READ: "0"
OS_WRITE: "1"
OS_MESG_NOBLOCK: "0"
OS_MESG_BLOCK: "1"
PI_STATUS_REG: "0x04600010"
PI_DRAM_ADDR_REG: "0x04600000"
PI_CART_ADDR_REG: "0x04600004"
PI_RD_LEN_REG: "0x04600008"
PI_WR_LEN_REG: "0x0460000C"
PI_STATUS_DMA_BUSY: "0x01"
PI_STATUS_IO_BUSY: "0x02"
PI_STATUS_ERROR: "0x04"
PI_STATUS_INTERRUPT: "0x08"
PI_BSD_DOM1_LAT_REG: "0x04600014"
PI_BSD_DOM1_PWD_REG: "0x04600018"
PI_BSD_DOM1_PGS_REG: "0x0460001C"
PI_BSD_DOM1_RLS_REG: "0x04600020"
PI_BSD_DOM2_LAT_REG: "0x04600024"
PI_BSD_DOM2_PWD_REG: "0x04600028"
PI_BSD_DOM2_PGS_REG: "0x0460002C"
PI_BSD_DOM2_RLS_REG: "0x04600030"
"""

PHASE_3_MACROS = """
G_ON: "1"
G_OFF: "0"
G_RM_AA_ZB_OPA_SURF: "0x00000000"
G_RM_AA_ZB_OPA_SURF2: "0x00000000"
G_RM_AA_ZB_XLU_SURF: "0x00000000"
G_RM_AA_ZB_XLU_SURF2: "0x00000000"
G_ZBUFFER: "0x00000001"
G_SHADE: "0x00000004"
G_CULL_BACK: "0x00002000"
G_CC_SHADE: "0x00000000"
"""

_N64_OS_STRUCT_BODIES = {
    "Mtx": """\
typedef union {
    struct { float mf[4][4]; } f;
    struct { s16   mi[4][4]; s16 pad; } i;
} Mtx;""",
    "OSContStatus": "typedef struct OSContStatus_s { u16 type; u8 status; u8 errno; } OSContStatus;",
    "OSContPad":    "typedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; u8 errno; } OSContPad;",
    "OSMesgQueue":  "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; s32 validCount; s32 first; s32 msgCount; OSMesg *msg; } OSMesgQueue;",
    "OSThread":     "typedef struct OSThread_s { struct OSThread_s *next; OSPri priority; struct OSThread_s **queue; struct OSThread_s *tlnext; u16 state; u16 flags; OSId id; int fp; long long int context[67]; } OSThread;",
    "OSMesgHdr":    "typedef struct { u16 type; u8 pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
    "OSPiHandle": """\
#ifndef __OSBlockInfo_DEFINED
#define __OSBlockInfo_DEFINED
typedef struct { u32 errStatus; void *dramAddr; void *C2Addr; u32 sectorSize; u32 C1ErrNum; u32 C1ErrSector[4]; } __OSBlockInfo;
#endif
#ifndef __OSTranxInfo_DEFINED
#define __OSTranxInfo_DEFINED
typedef struct { u32 cmdType; u16 transferMode; u16 blockNum; s32 sectorNum; u32 devAddr; u32 bmCtlShadow; u32 seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;
#endif
typedef struct OSPiHandle_s { struct OSPiHandle_s *next; u8 type; u8 latency; u8 pageSize; u8 relDuration; u8 pulse; u8 domain; u32 baseAddress; u32 speed; __OSTranxInfo transferInfo; } OSPiHandle;""",
    "OSIoMesg":  "typedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; u32 devAddr; u32 size; struct OSPiHandle_s *piHandle; } OSIoMesg;",
    "OSDevMgr":  "typedef struct OSDevMgr_s { s32 active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; s32 (*dma)(s32, u32, void *, u32); s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32); } OSDevMgr;",
    "OSPfs": """\
typedef struct OSPfs_s {
    struct OSIoMesg_s    ioMesgBuf;
    struct OSMesgQueue_s *queue;
    s32         channel;
    u8          activebank;
    u8          banks;
    u8          inodeTable[256];
    u8          dir[256];
    u32         label[8];
    s32         repairList[256];
    u32         version;
    u32         checksum;
    u32         inodeCacheIndex;
    u8          inodeCache[256];
} OSPfs;""",
    "OSTimer": "typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;",
    "LookAt":  "typedef struct { struct { float x, y, z; float pad; } l[2]; } LookAt;",
}

PHASE_3_STRUCTS = {
    "Gfx": "typedef struct { u32 words[2]; } Gfx;",
    "Vtx": "typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t; typedef union { Vtx_t v; long long int force_align[8]; } Vtx;",
    "OSViMode":    "typedef struct OSViMode_s { u32 type; u32 comRegs[4]; u32 fldRegs[2][7]; } OSViMode;",
    "OSViContext": "typedef struct OSViContext_s { u16 state; u16 retraceCount; void *framep; struct OSViMode_s *modep; u32 control; struct OSMesgQueue_s *msgq; OSMesg msg; } OSViContext;",
}

N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

N64_OS_OPAQUE_TYPES = {
    "OSPfs", "OSContStatus", "OSContPad", "OSPiHandle",
    "OSMesgQueue", "OSThread", "OSIoMesg", "OSTimer",
    "OSScTask", "OSTask", "OSScClient", "OSScKiller",
    "OSViMode", "OSViContext", "OSAiStatus", "OSMesgHdr",
    "OSPfsState", "OSPfsFile", "OSPfsDir", "OSDevMgr",
    "SPTask", "GBIarg",
}

N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
    "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
    "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

N64_KNOWN_GLOBALS = {
    "__osPiTable":       "struct OSPiHandle_s *__osPiTable;",
    "__osFlashHandle":   "struct OSPiHandle_s *__osFlashHandle;",
    "__osSfHandle":      "struct OSPiHandle_s *__osSfHandle;",
    "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
    "__osRunQueue":      "struct OSThread_s *__osRunQueue;",
    "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
}

CORE_PRIMITIVES = """\
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

/* N64 SDK Primitive Aliases */
typedef u32   OSIntMask;
typedef u64   OSTime;
typedef u32   OSId;
typedef s32   OSPri;
typedef void* OSMesg;
#endif
"""

# --- Utility Functions ---
def normalize_path(filepath: str) -> str:
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath:
            return filepath.split(marker)[-1]
    return filepath.lstrip("/") if filepath.startswith("/") else filepath

def strip_auto_preamble(content: str) -> str:
    lines = content.split('\n')
    result = []
    in_auto_block = False
    for line in lines:
        s = line.strip()
        if s.startswith("/* AUTO: forward decl"):
            in_auto_block = True
            continue
        if in_auto_block and re.match(r'(?:typedef\s+)?struct\s+\w+(?:_s)?\s+\w+\s*;', s):
            continue
        in_auto_block = False
        result.append(line)
    return '\n'.join(result)

def repair_unterminated_conditionals(content: str) -> str:
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
    if not remove:
        return content
    result = [line for i, line in enumerate(output) if i not in remove]
    return '\n'.join(result)

def _type_already_defined(tag: str, content: str) -> bool:
    if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content): return True
    if re.search(rf"\btypedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content): return True
    if f"{tag}_DEFINED" in content: return True
    return False

def _opaque_stub(tag: str, size: int = 64) -> str:
    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
    return (
        f"#ifndef {tag}_DEFINED\n"
        f"#define {tag}_DEFINED\n"
        f"struct {struct_tag} {{ long long int force_align[{size}]; }};\n"
        f"typedef struct {struct_tag} {tag};\n"
        f"#endif\n"
    )

def strip_redefinition(content: str, tag: str) -> str:
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
                if content[curr_idx] == '{': open_braces += 1
                elif content[curr_idx] == '}': open_braces -= 1
                curr_idx += 1
            semi_idx = content.find(';', curr_idx)
            if semi_idx != -1:
                content = content[:start_idx] + f"/* AUTO-STRIPPED RE-DEF: {tag} */\n" + content[semi_idx+1:]
                changed = True
                continue
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
        c_new, n = re.subn(rf"\bstruct\s+{re.escape(tag)}\s*;", f"/* STRIPPED FWD DECL: {tag} */", content)
        if n > 0: content, changed = c_new, True
    return content

# --- Error Registry ---
ERROR_REGISTRY: List[ErrorFix] = []

def register_error_fix(regex: str, category: str, handler: Callable, priority: int = 1):
    ERROR_REGISTRY.append(ErrorFix(regex, category, handler, priority))

def apply_fixes(categories: dict, registry: List[ErrorFix] = None) -> int:
    if registry is None:
        registry = ERROR_REGISTRY
    fixes = 0
    for error_fix in sorted(registry, key=lambda x: x.priority):
        for error in categories.get(error_fix.category, []):
            try:
                fixes += error_fix.handler(error)
            except Exception as e:
                logger.error(f"Failed to apply fix for {error}: {e}")
    return fixes

# --- Struct Injector ---
def resolve_struct_order(structs: Dict[str, str]) -> List[str]:
    graph = nx.DiGraph()
    for name, body in structs.items():
        graph.add_node(name)
        deps = extract_struct_deps(body)
        for dep in deps:
            if dep in structs:
                graph.add_edge(dep, name)
    return list(nx.topological_sort(graph))

def extract_struct_deps(body: str) -> List[str]:
    deps = set()
    for line in body.split('\n'):
        for word in line.split():
            if re.match(r'^[A-Z][A-Z0-9_]*$', word) and word not in N64_PRIMITIVES:
                deps.add(word)
    return list(deps)

# --- Log Scraper ---
def scrape_logs() -> Dict[str, List]:
    categories: Dict[str, List] = {
        "missing_types": [],
        "posix_reserved_conflict": [],
        "struct_redef": [],
        "typedef_redef": [],
        "undeclared_identifiers": set(),
        "implicit_func_stubs": set(),
        "need_struct_body": set(),
        "not_a_pointer": set(),
        "redefinition": [],
        "type_mismatch_globals": [],
        "conflict_typedef": set(),
        "missing_members": [],
        "audio_states": set(),
        "extraneous_brace": False,
        "conflicting_types": [],
        "missing_n64_types": [],
        "actor_pointer": [],
        "local_struct_fwd": [],
        "incomplete_sizeof": [],
        "static_conflict": [],
        "posix_conflict": [],
        "missing_globals": [],
        "undeclared_macros": set(),
        "implicit_func": set(),
        "undefined_symbols": set(),
        "undeclared_n64_types": [],
        "undeclared_gbi": set(),
    }

    log_candidates = [
        "Android/failed_files.log", "Android/full_build_log.txt",
        "full_build_log.txt", "build_log.txt", "Android/build_log.txt",
    ]
    try:
        for f in os.listdir("."):
            if f.endswith((".txt", ".log")):
                log_candidates.append(f)
    except Exception as e:
        logger.warning(f"Failed to list directory: {e}")

    for log_file in set(log_candidates):
        if not os.path.exists(log_file):
            continue
        try:
            with open(log_file, 'r', errors='replace') as f:
                content = f.read()
            # Missing types
            for m in re.finditer(r"(?m)^(/[^\s:]+\.(?:c|cpp)[^:]*):(?:\d+):(?:\d+):\s+error:\s+unknown type name '(\w+)'", content):
                filepath, tag = normalize_path(m.group(1)), m.group(2)
                if not any(isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag for x in categories["missing_types"]):
                    categories["missing_types"].append((filepath, tag))
            for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
                tag = m.group(1)
                if not any((isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag) or x==tag for x in categories["missing_types"]):
                    categories["missing_types"].append(tag)
            # POSIX static conflicts
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+static declaration of '(\w+)' follows non-static declaration", content):
                entry = (normalize_path(m.group(1)), m.group(2))
                if entry not in categories["posix_reserved_conflict"]:
                    categories["posix_reserved_conflict"].append(entry)
            # Struct / typedef redefinitions
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+redefinition of '(\w+)'", content):
                entry = (normalize_path(m.group(1)), m.group(2))
                if entry not in categories["struct_redef"]:
                    categories["struct_redef"].append(entry)
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+typedef redefinition.*?vs '(?:struct )?(\w+)'", content):
                entry = (normalize_path(m.group(1)), m.group(2))
                if entry not in categories["typedef_redef"]:
                    categories["typedef_redef"].append(entry)
            # Undeclared identifiers
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+use of undeclared identifier '(\w+)'", content):
                categories["undeclared_identifiers"].add(m.group(2))
            # Implicit functions
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+implicit declaration of function '(\w+)'", content):
                categories["implicit_func_stubs"].add(m.group(2))
            # Incomplete type member access
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+member access into incomplete type '(?:struct )?(\w+)'", content):
                categories["need_struct_body"].add(m.group(2))
            # Member reference not a pointer
            for m in re.finditer(r"error:\s+member reference (?:base )?type '[^']*' is not a (?:pointer|structure or union)\n([^\n]+)\n", content):
                snippet = m.group(1)
                for mm in re.finditer(r'([A-Za-z0-9_]+)(?:->|\.)', snippet):
                    categories["not_a_pointer"].add(mm.group(1))
            # Subscript of incomplete type
            for m in re.finditer(r"error:\s+subscript of pointer to incomplete type '(?:struct )?(\w+)'", content):
                categories["need_struct_body"].add(m.group(1))
            # Redeclaration with different type
            for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+redeclaration of '(\w+)' with a different type", content):
                filepath, var = normalize_path(m.group(1)), m.group(2)
                if (filepath, var) not in categories["type_mismatch_globals"]:
                    categories["type_mismatch_globals"].append((filepath, var))
        except Exception as e:
            logger.error(f"Failed to scrape {log_file}: {e}")
    return categories

# --- Handler Functions ---
def handle_missing_type(error: Union[Tuple[str, str], str]) -> int:
    fixes = 0
    if isinstance(error, tuple) and len(error) >= 2:
        filepath, tag = error[0], error[1]
    else:
        filepath, tag = None, error
    if tag in N64_PRIMITIVES:
        return 0
    types_content = read_file(TYPES_HEADER)
    if tag in N64_AUDIO_STATE_TYPES:
        if not _type_already_defined(tag, types_content):
            types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
            write_file(TYPES_HEADER, types_content)
            fixes += 1
    elif tag in N64_OS_OPAQUE_TYPES:
        if not _type_already_defined(tag, types_content):
            types_content += "\n" + _opaque_stub(tag, size=64)
            write_file(TYPES_HEADER, types_content)
            fixes += 1
    else:
        if not re.search(rf"\b{re.escape(tag)}\b", types_content):
            struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
            decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
            types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
            write_file(TYPES_HEADER, types_content)
            fixes += 1
    if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
        content = read_file(filepath)
        if 'n64_types.h"' not in content and '<n64_types.h>' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixes += 1
    return fixes

def handle_posix_conflict(error: Tuple[str, str]) -> int:
    filepath, func_name = error[0], error[1]
    if not func_name or not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
        return 0
    from collections import defaultdict
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
    if func_name in POSIX_RESERVED_NAMES:
        prefix = os.path.basename(filepath).split('.')[0]
        new_name = f"n64_{prefix}_{func_name}"
        define = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
        content = read_file(filepath)
        if define not in content:
            includes = list(re.finditer(r'#include\s+.*?\n', content))
            idx = includes[-1].end() if includes else 0
            content = content[:idx] + define + content[idx:]
            write_file(filepath, content)
            return 1
    return 0

# --- File I/O ---
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

# --- Main Script ---
def clean_conflicting_typedefs():
    if not os.path.exists(TYPES_HEADER):
        return
    content = original = read_file(TYPES_HEADER)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
    if content != original:
        write_file(TYPES_HEADER, content)

def ensure_types_header_base() -> str:
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
    for p in ["u8","s8","u16","s16","u32","s32","u64","s64","f32","f64","n64_bool",
              "OSIntMask","OSTime","OSId","OSPri","OSMesg"]:
        content = re.sub(rf"\btypedef\s+[^;]+\b{re.escape(p)}\s*;", "", content)
    for p in ["OSIntMask","OSTime","OSId","OSPri","OSMesg"]:
        content = re.sub(rf"(?:typedef\s+)?(?:struct\s+)?{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(p)}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s+{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{re.escape(p)}(?:_s)?\s*;\n?", "", content)
    content = content.replace("#pragma once", f"#pragma once\n{CORE_PRIMITIVES}", 1)
    content = repair_unterminated_conditionals(content)
    write_file(TYPES_HEADER, content)
    return content

def main():
    try:
        register_error_fix(r"unknown type name '(\w+)'", "missing_types", handle_missing_type, 1)
        register_error_fix(r"static declaration of '(\w+)'", "posix_reserved_conflict", handle_posix_conflict, 2)

        clean_conflicting_typedefs()
        types_content = ensure_types_header_base()
        categories = scrape_logs()
        fixes = apply_fixes(categories)
        logger.info(f"Applied {fixes} fixes.")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()