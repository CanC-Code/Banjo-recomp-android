#!/usr/bin/env python3
"""
N64 Recompilation Engine - Procedural Source Adaptation
A single-file, data-driven script for N64 type adaptation and error correction.
"""

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

# --- Embedded YAML Configs ---
PHASE1_MACROS_YAML = """
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

PHASE2_MACROS_YAML = """
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
""" + PHASE1_MACROS_YAML

PHASE3_MACROS_YAML = """
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
""" + PHASE2_MACROS_YAML

STRUCT_BODIES_YAML = """
Mtx: |
  typedef union {
      struct { float mf[4][4]; } f;
      struct { s16   mi[4][4]; s16 pad; } i;
  } Mtx;
OSContStatus: |
  typedef struct OSContStatus_s { u16 type; u8 status; u8 errno; } OSContStatus;
OSContPad: |
  typedef struct OSContPad_s { u16 button; s8 stick_x; s8 stick_y; u8 errno; } OSContPad;
OSMesgQueue: |
  typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; s32 validCount; s32 first; s32 msgCount; OSMesg *msg; } OSMesgQueue;
OSThread: |
  typedef struct OSThread_s { struct OSThread_s *next; OSPri priority; struct OSThread_s **queue; struct OSThread_s *tlnext; u16 state; u16 flags; OSId id; int fp; long long int context[67]; } OSThread;
OSMesgHdr: |
  typedef struct { u16 type; u8 pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;
OSPiHandle: |
  typedef struct OSPiHandle_s {
      struct OSPiHandle_s *next; u8 type; u8 latency; u8 pageSize; u8 relDuration; u8 pulse; u8 domain; u32 baseAddress; u32 speed;
      struct { u32 errStatus; void *dramAddr; void *C2Addr; u32 sectorSize; u32 C1ErrNum; u32 C1ErrSector[4]; } __OSBlockInfo;
      struct { u32 cmdType; u16 transferMode; u16 blockNum; s32 sectorNum; u32 devAddr; u32 bmCtlShadow; u32 seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;
  } OSPiHandle;
OSIoMesg: |
  typedef struct OSIoMesg_s { OSMesgHdr hdr; void *dramAddr; u32 devAddr; u32 size; struct OSPiHandle_s *piHandle; } OSIoMesg;
OSDevMgr: |
  typedef struct OSDevMgr_s { s32 active; struct OSThread_s *thread; struct OSMesgQueue_s *cmdQueue; struct OSMesgQueue_s *evtQueue; struct OSMesgQueue_s *acsQueue; s32 (*dma)(s32, u32, void *, u32); s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32); } OSDevMgr;
OSPfs: |
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
  } OSPfs;
OSTimer: |
  typedef struct OSTimer_s { struct OSTimer_s *next; struct OSTimer_s *prev; OSTime interval; OSTime value; struct OSMesgQueue_s *mq; OSMesg msg; } OSTimer;
LookAt: |
  typedef struct { struct { float x, y, z; float pad; } l[2]; } LookAt;
Gfx: |
  typedef struct { u32 words[2]; } Gfx;
Vtx: |
  typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
  typedef union { Vtx_t v; long long int force_align[8]; } Vtx;
OSViMode: |
  typedef struct OSViMode_s { u32 type; u32 comRegs[4]; u32 fldRegs[2][7]; } OSViMode;
OSViContext: |
  typedef struct OSViContext_s { u16 state; u16 retraceCount; void *framep; struct OSViMode_s *modep; u32 control; struct OSMesgQueue_s *msgq; OSMesg msg; } OSViContext;
"""

# --- Load YAML Configs ---
def load_yaml(yaml_str: str) -> dict:
    return yaml.safe_load(yaml_str)

PHASE1_MACROS = load_yaml(PHASE1_MACROS_YAML)
PHASE2_MACROS = load_yaml(PHASE2_MACROS_YAML)
PHASE3_MACROS = load_yaml(PHASE3_MACROS_YAML)
STRUCT_BODIES = load_yaml(STRUCT_BODIES_YAML)

# --- Constants ---
SDK_DEFINES_THESE = {"OSTask", "OSScTask"}
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

# --- Error Registry ---
ERROR_REGISTRY: List[ErrorFix] = []

def register_error_fix(regex: str, category: str, handler: Callable, priority: int = 1):
    ERROR_REGISTRY.append(ErrorFix(regex, category, handler, priority))

def apply_fixes(categories: dict, registry: List[ErrorFix]) -> int:
    fixes = 0
    for error_fix in sorted(registry, key=lambda x: x.priority):
        for error in categories.get(error_fix.category, []):
            fixes += error_fix.handler(error)
    return fixes

# --- Struct Injector ---
def resolve_struct_order(structs: Dict[str, str]) -> List[str]:
    graph = nx.DiGraph()
    for name, body in structs.items():
        graph.add_node(name)
        for dep in extract_struct_deps(body):
            if dep in structs:
                graph.add_edge(dep, name)
    return list(nx.topological_sort(graph))

def extract_struct_deps(body: str) -> List[str]:
    deps = []
    # Simple regex to find struct references
    for match in re.finditer(r"(?:struct|typedef)\s+(?:struct\s+)?(\w+)", body):
        if match.group(1) not in ["s", "u", "long", "short", "unsigned", "signed"]:
            deps.append(match.group(1))
    return deps

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

def _rename_posix_static(content: str, func_name: str, filepath: str) -> Tuple[str, bool]:
    prefix = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
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
    if re.search(rf"\btypedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content): return True
    if f"{tag}_DEFINED" in content: return True
    return False

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
    return '\n'.join([line for i, line in enumerate(output) if i not in remove])

# --- Log Scraper ---
def scrape_logs(categories: dict) -> None:
    log_candidates = [
        "Android/failed_files.log", "Android/full_build_log.txt",
        "full_build_log.txt", "build_log.txt", "Android/build_log.txt",
    ]
    try:
        for f in os.listdir("."):
            if f.endswith((".txt", ".log")): log_candidates.append(f)
    except Exception: pass

    for key in ["missing_types","posix_reserved_conflict","struct_redef","typedef_redef"]:
        categories.setdefault(key, [])
        if isinstance(categories[key], set): categories[key] = list(categories[key])
    for key in ["undeclared_identifiers","implicit_func_stubs","need_struct_body","not_a_pointer"]:
        categories.setdefault(key, set())
        if isinstance(categories[key], list): categories[key] = set(categories[key])

    mt  = categories["missing_types"]
    pc  = categories["posix_reserved_conflict"]
    sr  = categories["struct_redef"]
    ui  = categories["undeclared_identifiers"]
    ifs = categories["implicit_func_stubs"]
    nsb = categories["need_struct_body"]
    nap = categories["not_a_pointer"]

    for log_file in set(log_candidates):
        if not os.path.exists(log_file): continue
        content = read_file(log_file)
        for m in re.finditer(r"(?m)^(/[^\s:]+\.(?:c|cpp)[^:]*):(?:\d+):(?:\d+):\s+error:\s+unknown type name '(\w+)'", content):
            filepath, tag = normalize_path(m.group(1)), m.group(2)
            if not any(isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag for x in mt):
                mt.append((filepath, tag))
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            tag = m.group(1)
            if not any((isinstance(x,(list,tuple)) and len(x)>=2 and x[1]==tag) or x==tag for x in mt):
                mt.append(tag)
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+static declaration of '(\w+)' follows non-static declaration", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in pc: pc.append(entry)
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+redefinition of '(\w+)'", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in sr: sr.append(entry)
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+typedef redefinition.*?vs '(?:struct )?(\w+)'", content):
            entry = (normalize_path(m.group(1)), m.group(2))
            if entry not in sr: sr.append(entry)
        for m in re.finditer(r"n64_types\.h:\d+:\d+:\s+error:\s+typedef redefinition.*?'(?:struct )?(\w+)'", content):
            nsb.add(m.group(1))
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+use of undeclared identifier '(\w+)'", content):
            ui.add(m.group(2))
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+implicit declaration of function '(\w+)'", content):
            ifs.add(m.group(2))
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+member access into incomplete type '(?:struct )?(\w+)'", content):
            nsb.add(m.group(2))
        for m in re.finditer(r"error:\s+member reference (?:base )?type '.*?' is not a (?:pointer|structure or union)\n([^\n]+)\n", content):
            snippet = m.group(1)
            for mm in re.finditer(r'([A-Za-z0-9_]+)(?:->|\.)', snippet):
                nap.add(mm.group(1))
        for m in re.finditer(r"error:\s+subscript of pointer to incomplete type '(?:struct )?(\w+)'", content):
            nsb.add(m.group(1))

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
        with open(filepath, 'w') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write {filepath}: {e}")

# --- Main Fix Functions ---
def clean_conflicting_typedefs():
    if not os.path.exists(TYPES_HEADER): return
    content = original = read_file(TYPES_HEADER)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;", "", content)
    if content != original: write_file(TYPES_HEADER, content)

def ensure_types_header_base() -> str:
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content: content = "#pragma once\n" + content
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
    content = content.replace("#pragma once", f"#pragma once\n{_CORE_PRIMITIVES}", 1)
    content = repair_unterminated_conditionals(content)
    write_file(TYPES_HEADER, content)
    return content

_CORE_PRIMITIVES = """\
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

def apply_fixes(categories: dict, intelligence_level: int = 3) -> Tuple[int, set]:
    fixes = 0
    fixed_files = set()
    if intelligence_level >= 3:
        ACTIVE_MACROS = PHASE3_MACROS
        ACTIVE_STRUCTS = {k:v for k,v in STRUCT_BODIES.items() if k not in SDK_DEFINES_THESE}
    elif intelligence_level == 2:
        ACTIVE_MACROS = PHASE2_MACROS
        ACTIVE_STRUCTS = {k:v for k,v in STRUCT_BODIES.items() if k in N64_OS_OPAQUE_TYPES}
    else:
        ACTIVE_MACROS = PHASE1_MACROS
        ACTIVE_STRUCTS = {}

    known_type_tags: Set[str] = set()
    for item in categories.get("missing_types", []):
        if isinstance(item,(list,tuple)) and len(item)>=2: known_type_tags.add(item[1])
        elif isinstance(item, str): known_type_tags.add(item)
    known_type_tags.update(N64_OS_OPAQUE_TYPES)
    known_type_tags.update(ACTIVE_STRUCTS.keys())

    types_content = ensure_types_header_base()
    scrape_logs(categories)
    clean_conflicting_typedefs()

    # Macro scrubber
    for tag in known_type_tags:
        types_content, n1 = re.subn(rf"(?m)^\s*#ifndef {re.escape(tag)}\s*\n\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?", "", types_content)
        types_content, n2 = re.subn(rf"(?m)^\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?", "", types_content)
        if n1 + n2 > 0: fixes += 1
    if fixes > 0: write_file(TYPES_HEADER, types_content)

    # Inject struct bodies
    ordered_tags = resolve_struct_order(ACTIVE_STRUCTS)
    for tag in ordered_tags:
        body = ACTIVE_STRUCTS.get(tag)
        if not body: continue
        types_content = strip_redefinition(types_content, tag)
        types_content += "\n" + body + "\n"
    write_file(TYPES_HEADER, types_content)
    fixes += 1

    # Inject globals
    for glob, decl in N64_KNOWN_GLOBALS.items():
        if glob not in types_content:
            types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\nextern {decl}\n#endif\n"
    write_file(TYPES_HEADER, types_content)
    fixes += 1

    return fixes, fixed_files

# --- Main Entry Point ---
def main():
    categories = {
        "missing_types": [], "posix_reserved_conflict": [], "struct_redef": [],
        "typedef_redef": [], "undeclared_identifiers": set(), "implicit_func_stubs": set(),
        "need_struct_body": set(), "not_a_pointer": set()
    }
    try:
        fixes, fixed_files = apply_fixes(categories, intelligence_level=3)
        logger.info(f"Applied {fixes} fixes. Fixed files: {fixed_files}")
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()