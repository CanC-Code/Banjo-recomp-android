import os
import re
import logging
import sys
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional, Union

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# ---------------------------------------------------------------------------
# Constants 
# ---------------------------------------------------------------------------
try:
    from error_parser import (
        BRACE_MATCH, N64_STRUCT_BODIES as _EP_STRUCTS, KNOWN_MACROS as _EP_MACROS,
        KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES,
        read_file as _ep_read, write_file as _ep_write,
    )
    read_file  = _ep_read
    write_file = _ep_write
except ImportError:
    BRACE_MATCH = r"[^{}]*"
    _EP_STRUCTS = {}
    _EP_MACROS = {}

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

# ---------------------------------------------------------------------------
# Phase Definitions
# ---------------------------------------------------------------------------
PHASE_1_MACROS = {
    "OS_IM_1": "0x0001", "OS_IM_2": "0x0002",
    "OS_IM_3": "0x0004", "OS_IM_4": "0x0008",
    "OS_IM_5": "0x0010", "OS_IM_6": "0x0020",
    "OS_IM_7": "0x0040",
}

PHASE_2_MACROS = {
    **PHASE_1_MACROS,
    "DEVICE_TYPE_64DD": "0x06",
    "LEO_CMD_TYPE_0": "0",
    "LEO_CMD_TYPE_1": "1",
    "LEO_CMD_TYPE_2": "2",
    "LEO_SECTOR_MODE": "1",
    "LEO_TRACK_MODE": "2",
    "LEO_BM_CTL": "0x05000510",
    "LEO_BM_CTL_RESET": "0",
    "LEO_ERROR_29": "29",
    "OS_READ": "0",
    "OS_WRITE": "1",
    "OS_MESG_NOBLOCK": "0",
    "OS_MESG_BLOCK": "1",
}

_N64_OS_STRUCT_BODIES = {
    "Mtx": """\
typedef union {
    struct { float mf[4][4]; } f;
    struct { s16   mi[4][4]; s16 pad; } i;
} Mtx;""",

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
    struct OSPfsState_s  *status;
    u32         version;
    u32         checksum;
    u32         inodeCacheIndex;
    u8          inodeCache[256];
} OSPfs;""",

    "OSContStatus": """\
typedef struct OSContStatus_s {
    u16 type;
    u8  status;
    u8  errno;
} OSContStatus;""",

    "OSContPad": """\
typedef struct OSContPad_s {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;""",

    "OSPiHandle": """\
#ifndef __OSBlockInfo_DEFINED
#define __OSBlockInfo_DEFINED
typedef struct {
    u32 errStatus;
    void *dramAddr;
    void *C2Addr;
    u32 sectorSize;
    u32 C1ErrNum;
    u32 C1ErrSector[4];
} __OSBlockInfo;
#endif

#ifndef __OSTranxInfo_DEFINED
#define __OSTranxInfo_DEFINED
typedef struct {
    u32 cmdType;
    u16 transferMode;
    u16 blockNum;
    s32 sectorNum;
    u32 devAddr;
    u32 bmCtlShadow;
    u32 seqCtlShadow;
    __OSBlockInfo block[2];
} __OSTranxInfo;
#endif

typedef struct OSPiHandle_s {
    struct OSPiHandle_s *next;
    u8      type;
    u8      latency;
    u8      pageSize;
    u8      relDuration;
    u8      pulse;
    u8      domain;
    u32     baseAddress;
    u32     speed;
    __OSTranxInfo transferInfo;
} OSPiHandle;""",

    "OSMesgQueue": """\
typedef struct OSMesgQueue_s {
    struct OSThread_s *mtqueue;
    struct OSThread_s *fullqueue;
    s32          validCount;
    s32          first;
    s32          msgCount;
    OSMesg      *msg;
} OSMesgQueue;""",

    "OSThread": """\
typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri              priority;
    struct OSThread_s **queue;
    struct OSThread_s *tlnext;
    u16                state;
    u16                flags;
    OSId               id;
    int                fp;
    long long int      context[67];
} OSThread;""",

    "OSMesgHdr": """\
typedef struct {
    u16 type;
    u8  pri;
    struct OSMesgQueue_s *retQueue;
} OSMesgHdr;""",

    "OSIoMesg": """\
typedef struct OSIoMesg_s {
    OSMesgHdr   hdr;
    void        *dramAddr;
    u32         devAddr;
    u32         size;
    struct OSPiHandle_s *piHandle;
} OSIoMesg;""",

    "OSDevMgr": """\
typedef struct OSDevMgr_s {
    s32 active;
    struct OSThread_s *thread;
    struct OSMesgQueue_s *cmdQueue;
    struct OSMesgQueue_s *evtQueue;
    struct OSMesgQueue_s *acsQueue;
    s32 (*dma)(s32, u32, void *, u32);
    s32 (*edma)(struct OSPiHandle_s *, s32, u32, void *, u32);
} OSDevMgr;""",

    "OSTimer": """\
typedef struct OSTimer_s {
    struct OSTimer_s *next;
    struct OSTimer_s *prev;
    OSTime            interval;
    OSTime            value;
    struct OSMesgQueue_s *mq;
    OSMesg            msg;
} OSTimer;""",

    "OSScTask": """\
typedef struct OSScTask_s {
    struct OSScTask_s *next;
    u32                state;
    u32                flags;
    struct OSTask_s   *list;
    struct OSMesgQueue_s *msgQ;
    OSMesg             msg;
    u8                *framebuffer;
    u32                tid;
} OSScTask;""",

    "OSTask": """\
typedef struct OSTask_s {
    u32 type;
    u32 flags;
    u64 *ucode_boot;
    u32  ucode_boot_size;
    u64 *ucode;
    u32  ucode_size;
    u64 *ucode_data;
    u32  ucode_data_size;
    u64 *dram_stack;
    u32  dram_stack_size;
    u64 *output_buff;
    u64 *output_buff_size;
    u64 *data_ptr;
    u32  data_size;
    u64 *yield_data_ptr;
    u32  yield_data_size;
} OSTask;""",

    "LookAt": """\
typedef struct {
    struct {
        float x, y, z;
        float pad;
    } l[2];
} LookAt;""",
}

# ---------------------------------------------------------------------------
# N64 OS type sets
# ---------------------------------------------------------------------------
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool",
    "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
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

# ---------------------------------------------------------------------------
# Canonical primitives block
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_path(filepath: str) -> str:
    """Converts absolute CI/CD paths to local relative paths."""
    # Look for common project root folder names
    markers = ["Banjo-recomp-android/", "Android/app/"]
    for marker in markers:
        if marker in filepath:
            return filepath.split(marker)[-1]
    
    # If it starts with a slash but we couldn't find a marker, try stripping the leading slash
    if filepath.startswith("/"):
        return filepath.lstrip("/")
    return filepath

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
    prefix   = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define   = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
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
    if re.search(rf"\btypedef\s+(?:struct|union)\s+\w*\s*\{{", content):
        if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content):
            return True
    if re.search(rf"\btypedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content):
        return True
    if f"{tag}_DEFINED" in content:
        return True
    return False

def strip_redefinition(content: str, tag: str) -> str:
    changed = True
    while changed:
        changed = False

        # 1. Explicit tagged struct (struct TAG { ... })
        pattern1 = re.compile(rf"\bstruct\s+{re.escape(tag)}\s*\{{")
        match = pattern1.search(content)
        if match:
            start_idx = match.start()
            pre = content[:start_idx].rstrip()
            if pre.endswith("typedef"):
                start_idx = pre.rfind("typedef")

            brace_idx = content.find('{', match.start())
            open_braces = 1
            curr_idx = brace_idx + 1
            while curr_idx < len(content) and open_braces > 0:
                if content[curr_idx] == '{': open_braces += 1
                elif content[curr_idx] == '}': open_braces -= 1
                curr_idx += 1

            semi_idx = content.find(';', curr_idx)
            if semi_idx != -1:
                content = content[:start_idx] + f"/* AUTO-STRIPPED RE-DEF: {tag} */\n" + content[semi_idx+1:]
                changed = True
                continue

        # 2. Typedef alias (typedef struct { ... } TAG;)
        idx = 0
        while True:
            match = re.search(r"\btypedef\s+struct\b[^{]*\{", content[idx:])
            if not match:
                break
            start_idx = idx + match.start()
            brace_idx = content.find('{', start_idx)

            open_braces = 1
            curr_idx = brace_idx + 1
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

        # 3. Loose typedefs / fwd decls
        c_new, n = re.subn(rf"\btypedef\s+(?:struct\s+)?[A-Za-z0-9_]+\s+{re.escape(tag)}\s*;", f"/* STRIPPED LOOSE TYPEDEF: {tag} */", content)
        if n > 0:
            content = c_new
            changed = True

        c_new, n = re.subn(rf"\bstruct\s+{re.escape(tag)}\s*;", f"/* STRIPPED FWD DECL: {tag} */", content)
        if n > 0:
            content = c_new
            changed = True

    return content

# ---------------------------------------------------------------------------
# ensure_types_header_base
# ---------------------------------------------------------------------------
def clean_conflicting_typedefs():
    if not os.path.exists(TYPES_HEADER):
        return
    content = original = read_file(TYPES_HEADER)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(
            rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;",
            "", content)
        content = re.sub(rf"typedef\s+struct\s+{p}(?:_s)?\s*\{{[^}}]*\}}\s*{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{p}\s*;", "", content)
    if content != original:
        write_file(TYPES_HEADER, content)

def ensure_types_header_base() -> str:
    if os.path.exists(TYPES_HEADER):
        original_content = read_file(TYPES_HEADER)
        content = original_content
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        original_content = ""
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    content = re.sub(
        r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?",
        "", content)

    primitive_list = ["u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
                      "f32", "f64", "n64_bool",
                      "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]
    for p in primitive_list:
        content = re.sub(rf"\btypedef\s+[^;]+\b{re.escape(p)}\s*;", "", content)

    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(
            rf"(?:typedef\s+)?(?:struct\s+)?{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(p)}\s*)?;?\n?",
            "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s+{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{re.escape(p)}(?:_s)?\s*;\n?", "", content)

    content = content.replace("#pragma once", f"#pragma once\n{_CORE_PRIMITIVES}", 1)

    if content != original_content:
        write_file(TYPES_HEADER, content)
    return content

# ---------------------------------------------------------------------------
# Log scraper
# ---------------------------------------------------------------------------
def _scrape_logs_into_categories(categories: dict) -> None:
    log_candidates = [
        "Android/failed_files.log",
        "Android/full_build_log.txt",
        "full_build_log.txt",
        "build_log.txt",
        "Android/build_log.txt",
    ]
    try:
        for f in os.listdir("."):
            if f.endswith((".txt", ".log")):
                log_candidates.append(f)
    except Exception:
        pass

    if "missing_types" not in categories: categories["missing_types"] = []
    elif isinstance(categories["missing_types"], set): categories["missing_types"] = list(categories["missing_types"])
    mt = categories["missing_types"]

    if "posix_reserved_conflict" not in categories: categories["posix_reserved_conflict"] = []
    elif isinstance(categories["posix_reserved_conflict"], set): categories["posix_reserved_conflict"] = list(categories["posix_reserved_conflict"])
    pc = categories["posix_reserved_conflict"]

    if "struct_redef" not in categories: categories["struct_redef"] = []
    elif isinstance(categories["struct_redef"], set): categories["struct_redef"] = list(categories["struct_redef"])
    sr = categories["struct_redef"]

    for log_file in set(log_candidates):
        if not os.path.exists(log_file):
            continue
        content = read_file(log_file)

        # Missing Types
        for m in re.finditer(
                r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+unknown type name '(\w+)'", content):
            filepath = normalize_path(m.group(1))
            tag = m.group(2)
            if (filepath, tag) not in mt and not any(isinstance(x, (list, tuple)) and len(x) >= 2 and x[1] == tag for x in mt):
                mt.append((filepath, tag))

        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            tag = m.group(1)
            if not any((isinstance(x, (list, tuple)) and len(x) >= 2 and x[1] == tag) or x == tag for x in mt):
                mt.append(tag)

        # POSIX Conflicts
        for m in re.finditer(
                r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+static declaration of '(\w+)' follows non-static declaration", content):
            filepath = normalize_path(m.group(1))
            func = m.group(2)
            if (filepath, func) not in pc:
                pc.append((filepath, func))

        # Struct/Typedef Redefinitions
        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+redefinition of '(\w+)'", content):
            filepath = normalize_path(m.group(1))
            tag = m.group(2)
            if (filepath, tag) not in sr:
                sr.append((filepath, tag))

        for m in re.finditer(r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+typedef redefinition with different types .*? vs '(?:struct )?(\w+)'", content):
            filepath = normalize_path(m.group(1))
            tag = m.group(2)
            if (filepath, tag) not in sr:
                sr.append((filepath, tag))

# ---------------------------------------------------------------------------
# Main fix dispatcher (Now respects Intelligence Level)
# ---------------------------------------------------------------------------
def apply_fixes(categories: dict, intelligence_level: int = 1) -> Tuple[int, set]:
    fixes       = 0
    fixed_files = set()

    # Determine Active Dictionaries Based on Intelligence
    ACTIVE_MACROS = PHASE_2_MACROS if intelligence_level >= 2 else PHASE_1_MACROS
    ACTIVE_STRUCTS = _N64_OS_STRUCT_BODIES if intelligence_level >= 2 else {}
    for _k, _v in _EP_STRUCTS.items():
        ACTIVE_STRUCTS[_k] = _v

    _scrape_logs_into_categories(categories)

    clean_conflicting_typedefs()
    types_content = ensure_types_header_base()

    # ------------------------------------------------------------------
    # Intelligence Level 2: Regret Cleanup
    # ------------------------------------------------------------------
    if intelligence_level >= 2:
        original_types = types_content
        # We now know certain globals are actually macros or structs. 
        # Remove any blind Phase 1 "extern long long int" guesses.
        scrub_targets = set(ACTIVE_STRUCTS.keys()) | N64_OS_OPAQUE_TYPES | set(ACTIVE_MACROS.keys()) | {"__osPiTable"}

        for target in scrub_targets:
            # Match #ifndef / #define / extern / #endif blocks
            types_content = re.sub(
                rf"(?m)^#ifndef {re.escape(target)}_DEFINED\n#define {re.escape(target)}_DEFINED\nextern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?;\n#endif\n?", 
                "", types_content)
            # Match stray externs
            types_content = re.sub(
                rf"(?m)^extern\s+(?:long\s+long\s+int|void\*)\s+{re.escape(target)}(?:\[\])?;\n?", 
                "", types_content)

        if types_content != original_types:
            logger.info("🧹 Phase 2 Cleanup: Removed incorrect Phase 1 primitive guesses.")
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Macro scrubber
    known_type_tags: Set[str] = set()
    for item in categories.get("missing_types", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2: known_type_tags.add(item[1])
        elif isinstance(item, str): known_type_tags.add(item)
    for tag in categories.get("need_struct_body", []):
        if isinstance(tag, str): known_type_tags.add(tag)
    for item in categories.get("incomplete_sizeof", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2: known_type_tags.add(item[1])
    for tag in categories.get("conflict_typedef", []):
        if isinstance(tag, str): known_type_tags.add(tag)

    known_type_tags.update(N64_OS_OPAQUE_TYPES)
    known_type_tags.update(ACTIVE_STRUCTS.keys())

    macros_cleaned = False
    for tag in known_type_tags:
        p1 = rf"(?m)^\s*#ifndef {re.escape(tag)}\s*\n\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(p1, "", types_content)
        p2 = rf"(?m)^\s*#define {re.escape(tag)} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
        types_content, n2 = re.subn(p2, "", types_content)
        if n1 + n2 > 0:
            macros_cleaned = True
            fixes += 1
    if macros_cleaned:
        write_file(TYPES_HEADER, types_content)

    # Conflict typedef cleanup
    for type_name in sorted(categories.get("conflict_typedef", [])):
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(?:typedef\s+)?(?:struct\s+)?{re.escape(type_name)}\s*\{{[^}}]*\}}\s*{re.escape(type_name)}?\s*;\n?"
        new_types, n = re.subn(pattern, "", types_content)
        new_types = re.sub(
            rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{re.escape(type_name)}\s*;",
            "", new_types)
        if n > 0:
            if f"struct {type_name}_s {{" not in new_types:
                new_types += f"\nstruct {type_name}_s {{ long long int force_align[64]; }};\n"
            write_file(TYPES_HEADER, new_types)
            types_content = new_types
            fixes += 1

    # Missing members injection
    array_names = {"id", "label", "name", "buffer", "data", "str", "string", "temp"}
    for item in sorted(categories.get("missing_members", [])):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        struct_name, member_name = item[0], item[1]
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(struct\s+{re.escape(struct_name)}\s*\{{)([^}}]*?)(\}})"

        def inject_member(match, mn=member_name, an=array_names):
            body = match.group(2)
            if mn not in body:
                if mn in an: field = f"    unsigned char {mn}[128]; /* AUTO-ARRAY */\n"
                elif "ptr" in mn.lower() or "func" in mn.lower() or "cb" in mn.lower(): field = f"    void* {mn}; /* AUTO-POINTER */\n"
                else: field = f"    long long int {mn};\n"
                return f"{match.group(1)}{body}{field}{match.group(3)}"
            return match.group(0)

        if re.search(pattern, types_content):
            new_types, n = re.subn(pattern, inject_member, types_content)
            if n > 0:
                write_file(TYPES_HEADER, new_types)
                fixes += 1
        else:
            mn = member_name
            if mn in array_names: field = f"unsigned char {mn}[128]; /* AUTO-ARRAY */"
            elif "ptr" in mn.lower() or "func" in mn.lower() or "cb" in mn.lower(): field = f"void* {mn}; /* AUTO-POINTER */"
            else: field = f"long long int {mn};"
            types_content += (
                f"\nstruct {struct_name} {{\n    {field}\n"
                f"    long long int force_align[64];\n}};\n"
            )
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Variable redefinitions
    for item in sorted(categories.get("redefinition", [])):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        filepath, var = item[0], item[1]
        if os.path.exists(filepath):
            content = read_file(filepath)
            new_content, n = re.subn(
                rf"^(.*?\b{re.escape(var)}\b.*?;)",
                r"/* AUTO-REMOVED REDEF: \1 */",
                content, flags=re.MULTILINE)
            if n > 0:
                write_file(filepath, new_content)
                fixed_files.add(filepath)
                fixes += 1

    # Missing types
    for item in sorted(categories.get("missing_types", []), key=str):
        if isinstance(item, (list, tuple)) and len(item) >= 2: filepath, tag = item[0], item[1]
        elif isinstance(item, str): filepath, tag = None, item
        else: continue

        if not isinstance(tag, str): continue

        types_content = read_file(TYPES_HEADER)

        if tag in N64_PRIMITIVES:
            pass  
        elif tag in N64_AUDIO_STATE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                write_file(TYPES_HEADER, types_content)
                fixes += 1
        elif tag in ACTIVE_STRUCTS:
            categories.setdefault("need_struct_body", set()).add(tag)
        elif tag in N64_OS_OPAQUE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += "\n" + _opaque_stub(tag, size=64)
                write_file(TYPES_HEADER, types_content)
                fixes += 1
        else:
            if not re.search(rf"\b{re.escape(tag)}\b", types_content):
                struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                decl = (
                    f"struct {struct_tag} {{ long long int force_align[64]; }};\n"
                    f"typedef struct {struct_tag} {tag};\n"
                )
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content)
                fixed_files.add(TYPES_HEADER)
                fixes += 1

        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                fixed_files.add(filepath)
                fixes += 1

    # Explicit audio state category
    if categories.get("unknown_audio_state_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        for t in sorted(categories["unknown_audio_state_types"]):
            if not isinstance(t, str) or t not in N64_AUDIO_STATE_TYPES: continue
            if not _type_already_defined(t, types_content):
                types_content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
                added = True
        if added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Extraneous brace cleanup
    if categories.get("extraneous_brace"):
        types_content = read_file(TYPES_HEADER)
        original = types_content
        types_content = re.sub(
            r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n",
            "", types_content)
        types_content = re.sub(
            r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{",
            r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Conflicting implicit-type prototypes
    for item in sorted(categories.get("conflicting_types", []), key=str):
        if not isinstance(item, (list, tuple)) or len(item) < 2: continue
        filepath, func = item[0], item[1]
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        pattern = rf"(?:^|\n)([A-Za-z_][A-Za-z0-9_\s\*]+?)\s+\b{re.escape(func)}\s*\([^;{{]*\)\s*\{{"
        match = re.search(pattern, content)
        if match:
            sig_full = match.group(0)
            prototype = sig_full[:sig_full.rfind('{')].strip() + ";"
            if prototype not in content:
                includes = list(re.finditer(r"#include\s+.*?\n", content))
                injection = f"\n/* AUTO: resolve conflicting implicit type */\n{prototype}\n"
                idx = includes[-1].end() if includes else 0
                content = content[:idx] + injection + content[idx:]
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # Missing n64_types.h include
    for item in sorted(categories.get("missing_n64_types", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'n64_types.h"' not in content and '<n64_types.h>' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath)
            fixes += 1

    # Actor pointer injection
    for item in sorted(categories.get("actor_pointer", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath): continue
        content = original = read_file(filepath)
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # Local struct forward declarations
    if categories.get("local_struct_fwd"):
        file_to_types: dict = defaultdict(set)
        for item in categories["local_struct_fwd"]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                file_to_types[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content: fwd_lines.append(fwd_decl)
            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n"
                write_file(filepath, injection + content)
                fixed_files.add(filepath)
                fixes += 1

    # Typedef / struct redefinitions
    fixd_files: set = set()
    for item in categories.get("typedef_redef", []):
        if isinstance(item, (list, tuple)) and len(item) >= 1: fixd_files.add(item[0])
    for item in categories.get("struct_redef", []):
        if isinstance(item, (list, tuple)) and len(item) >= 1: fixd_files.add(item[0])

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content  = read_file(filepath)
        original = content
        content  = strip_auto_preamble(content)

        for item in categories.get("struct_redef", []):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            fp2, tag = item[0], item[1]
            if fp2 != filepath: continue
            content = strip_redefinition(content, tag)

        for item in categories.get("typedef_redef", []):
            if not isinstance(item, (list, tuple)) or len(item) < 3: continue
            fp2, type1, type2 = item[0], item[1], item[2]
            if fp2 != filepath: continue
            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2): continue

            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            anon_pat = rf"typedef\s+struct\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_pat, content):
                def _anon_sub(m, tt=target_tag): return f"typedef struct {tt} {{{m.group(1)}}} {m.group(2)};"
                content, _ = re.subn(anon_pat, _anon_sub, content)
            else:
                bad_pat = rf"(?:typedef\s+)?struct\s+{re.escape(alias)}\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
                if re.search(bad_pat, content):
                    def _bad_sub(m, tt=target_tag): return f"typedef struct {tt} {{{m.group(1)}}} {m.group(2)};"
                    content, _ = re.subn(bad_pat, _bad_sub, content)
                else:
                    content, _ = re.subn(r"\bstruct\s+" + re.escape(alias) + r"\b", f"struct {target_tag}", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # Incomplete sizeof
    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen: set = set()
        for item in categories["incomplete_sizeof"]:
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            filepath, tag = item[0], item[1]
            if tag in seen: continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in ACTIVE_STRUCTS: continue
            is_sdk = (tag.isupper()
                      or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_"))
                      or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Static / POSIX name conflicts
    seen_static: set = set()
    for cat in ["static_conflict", "posix_conflict", "posix_reserved_conflict"]:
        for item in categories.get(cat, []):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            filepath, func_name = item[0], item[1]
            key = (filepath, func_name)
            if key in seen_static: continue
            seen_static.add(key)
            if not func_name or not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath)
                    fixes += 1
                continue
            prefix    = os.path.basename(filepath).split('.')[0]
            macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
            if macro_fix not in content:
                anchor  = '#include "ultra/n64_types.h"'
                content = (content.replace(anchor, anchor + macro_fix)
                           if anchor in content else macro_fix + content)
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # Undeclared macros
    if categories.get("undeclared_macros"):
        types_content = read_file(TYPES_HEADER)
        macros_added  = False
        for macro in sorted(categories["undeclared_macros"]):
            if not isinstance(macro, str): continue
            if macro in KNOWN_FUNCTION_MACROS:
                defn = KNOWN_FUNCTION_MACROS[macro]
                if defn not in types_content:
                    types_content += f"\n{defn}\n"
                    macros_added = True
            elif macro in ACTIVE_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {ACTIVE_MACROS[macro]}\n#endif\n"
                    macros_added = True
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Implicit function declarations → system headers
    if categories.get("implicit_func"):
        math_funcs   = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        types_content  = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if not isinstance(func, str): continue
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs:   header = "<stdlib.h>"
            else:                        continue
            if f"#include {header}" not in types_content:
                types_content  = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Undefined linker symbols → stubs
    if categories.get("undefined_symbols"):
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace(
                        "add_library(", "add_library(\n        ultra/n64_stubs.c")
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added    = False
        for sym in sorted(categories["undefined_symbols"]):
            if not isinstance(sym, str): continue
            if sym.startswith("_Z") or "vtable" in sym: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    # Audio-state opaque types
    if categories.get("audio_states"):
        types_content = read_file(TYPES_HEADER)
        audio_added   = False
        for t in sorted(categories["audio_states"]):
            if not isinstance(t, str): continue
            if not _type_already_defined(t, types_content):
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Undeclared N64 platform types
    if categories.get("undeclared_n64_types"):
        types_content = read_file(TYPES_HEADER)
        k_added = False
        for item in sorted(categories["undeclared_n64_types"], key=str):
            if isinstance(item, (list, tuple)) and len(item) >= 2: filepath, t = item[0], item[1]
            elif isinstance(item, str): filepath, t = None, item
            else: continue
            if not isinstance(t, str) or t in N64_PRIMITIVES: continue
            if t in ACTIVE_STRUCTS:
                categories.setdefault("need_struct_body", set()).add(t)
            elif t in N64_OS_OPAQUE_TYPES:
                if not _type_already_defined(t, types_content):
                    types_content += "\n" + _opaque_stub(t, size=64)
                    k_added = True
            elif not re.search(rf"\b{re.escape(t)}\b", types_content):
                struct_tag = f"{t}_s" if not t.endswith("_s") else t
                decl = (
                    f"struct {struct_tag} {{ long long int force_align[64]; }};\n"
                    f"typedef struct {struct_tag} {t};\n"
                )
                types_content += f"\n#ifndef {t}_DEFINED\n#define {t}_DEFINED\n{decl}#endif\n"
                k_added = True
            if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                c = read_file(filepath)
                if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                    fixed_files.add(filepath)
                    fixes += 1
        if k_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs)
                fixes += 1

    # Undeclared GBI constants
    if categories.get("undeclared_gbi"):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if not isinstance(ident, str): continue
            if ident in ACTIVE_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {ACTIVE_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in ACTIVE_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                gbi_added = True
        if gbi_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Full struct bodies for known N64 types
    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added  = False
        for tag in sorted(categories["need_struct_body"]):
            if not isinstance(tag, str): continue
            body = ACTIVE_STRUCTS.get(tag)
            if not body:
                if tag in N64_OS_OPAQUE_TYPES and not _type_already_defined(tag, types_content):
                    types_content += "\n" + _opaque_stub(tag)
                    bodies_added = True
                continue
            if _type_already_defined(tag, types_content): continue
            if tag == "LookAt":
                types_content = re.sub(r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__Light_t\s*;\n?", "", types_content)
                types_content = re.sub(r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__LookAtDir\s*;\n?", "", types_content)
            if tag == "Mtx":
                types_content = re.sub(r"(?m)^typedef\s+union\s*\{[^}]*\}\s*__Mtx_data\s*;\n?", "", types_content)
            types_content = re.sub(
                rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(tag)}\s*)?;?\n?",
                "", types_content)
            types_content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(tag)}\s*;\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;\n?", "", types_content)
            types_content = re.sub(rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
            types_content = re.sub(rf"#ifndef {re.escape(tag)}_DEFINED[\s\S]*?#endif\n?", "", types_content)
            types_content += "\n" + body + "\n"
            bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Local forward-only declarations
    if categories.get("local_fwd_only"):
        file_to_types2: dict = defaultdict(set)
        for item in categories["local_fwd_only"]:
            if isinstance(item, (list, tuple)) and len(item) >= 2: file_to_types2[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types2.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{[^}}]*\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
                fwd_decl = f"typedef struct {t}_s {t};"
                if re.search(body_pattern, content): fwd = f"/* AUTO: forward decl for type defined below */\n{fwd_decl}\n"
                else: fwd = f"/* AUTO: forward declarations */\n{fwd_decl}\n"
                if fwd_decl not in content:
                    content = fwd + content
                    changed = True
            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # Missing global extern declarations
    if categories.get("missing_globals"):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for item in sorted(categories["missing_globals"], key=str):
            if isinstance(item, (list, tuple)) and len(item) >= 2: _, glob = item[0], item[1]
            elif isinstance(item, str): glob = item
            else: continue
            if glob == "actor": continue
            if (f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content):
                decl = (f"extern void* {glob};" if glob.endswith(("_ptr", "_p")) else f"extern long long int {glob};")
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    return fixes, fixed_files
