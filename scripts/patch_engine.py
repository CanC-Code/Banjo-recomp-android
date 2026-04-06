import os
import re
import logging
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional, Union

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# ---------------------------------------------------------------------------
# Constants — try to import from error_parser, fall back to self-contained
# ---------------------------------------------------------------------------
try:
    from error_parser import (
        BRACE_MATCH, N64_STRUCT_BODIES, KNOWN_MACROS,
        KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES,
        read_file as _ep_read, write_file as _ep_write,
    )
    read_file  = _ep_read
    write_file = _ep_write
except ImportError:
    BRACE_MATCH = r"[^{}]*"

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

    KNOWN_MACROS = {
        "OS_IM_1": "0x0001", "OS_IM_2": "0x0002",
        "OS_IM_3": "0x0004", "OS_IM_4": "0x0008",
        "OS_IM_5": "0x0010", "OS_IM_6": "0x0020",
        "OS_IM_7": "0x0040",
    }
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
    N64_STRUCT_BODIES = {}

# ---------------------------------------------------------------------------
# Full N64 OS struct body definitions
# These cover ALL types that appear in bamotor.c and similar core1 files.
# ---------------------------------------------------------------------------
_N64_OS_STRUCT_BODIES = {
    "Mtx": """\
typedef union {
    struct { float mf[4][4]; } f;
    struct { s16   mi[4][4]; s16 pad; } i;
} Mtx;""",

    "OSPfs": """\
typedef struct OSPfs_s {
    OSIoMesg    ioMesgBuf;
    OSMesgQueue *queue;
    s32         channel;
    u8          activebank;
    u8          banks;
    u8          inodeTable[PFS_INODE_TABLE_SIZE];
    u8          dir[PFS_FILE_TABLE_SIZE * sizeof(OSPfsState)];
    u32         label[PFS_LABEL_SIZE / sizeof(u32)];
    s32         repairList[PFS_INODE_TABLE_SIZE];
    OSPfsState  *status;
    u32         version;
    u32         checksum;
    u32         inodeCacheIndex;
    u8          inodeCache[PFS_ONE_PAGE];
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
    OSMesg  transferInfo[18];
} OSPiHandle;""",

    "OSMesgQueue": """\
typedef struct OSMesgQueue_s {
    OSThread    *mtqueue;
    OSThread    *fullqueue;
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

    "OSIoMesg": """\
typedef struct OSIoMesg_s {
    OSMesg      hdr;
    OSMesg      dramAddr;
    u32         devAddr;
    size_t      size;
    OSPiHandle *hHandle;
} OSIoMesg;""",

    "OSTimer": """\
typedef struct OSTimer_s {
    struct OSTimer_s *next;
    struct OSTimer_s *prev;
    OSTime            interval;
    OSTime            value;
    OSMesgQueue      *mq;
    OSMesg            msg;
} OSTimer;""",

    "OSScTask": """\
typedef struct OSScTask_s {
    struct OSScTask_s *next;
    u32                state;
    u32                flags;
    struct OSTask_s   *list;
    OSMesgQueue       *msgQ;
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

# Merge into N64_STRUCT_BODIES (error_parser entries take priority)
for _k, _v in _N64_OS_STRUCT_BODIES.items():
    if _k not in N64_STRUCT_BODIES:
        N64_STRUCT_BODIES[_k] = _v

# ---------------------------------------------------------------------------
# N64 OS type sets
# ---------------------------------------------------------------------------

# Types whose definitions are FULLY covered by the primitives block
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool",
    "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

# N64 OS types that need opaque struct stubs when their full body isn't known
N64_OS_OPAQUE_TYPES = {
    "OSPfs", "OSContStatus", "OSContPad", "OSPiHandle",
    "OSMesgQueue", "OSThread", "OSIoMesg", "OSTimer",
    "OSScTask", "OSTask", "OSScClient", "OSScKiller",
    "OSViMode", "OSViContext", "OSAiStatus",
    "OSPfsState", "OSPfsFile", "OSPfsDir",
    "SPTask", "GBIarg",
}

# Audio DSP state types — opaque stubs only
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
    """Return an opaque struct stub for an unknown N64 type."""
    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
    return (
        f"#ifndef {tag}_DEFINED\n"
        f"#define {tag}_DEFINED\n"
        f"struct {struct_tag} {{ long long int force_align[{size}]; }};\n"
        f"typedef struct {struct_tag} {tag};\n"
        f"#endif\n"
    )


def _type_already_defined(tag: str, content: str) -> bool:
    """True if content already has a meaningful definition of tag."""
    # Check typedef struct ... tag ;
    if re.search(rf"\btypedef\s+(?:struct|union)\s+\w*\s*\{{", content):
        if re.search(rf"\}}\s*{re.escape(tag)}\s*;", content):
            return True
    # Check typedef struct TAG_s TAG;
    if re.search(rf"\btypedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;", content):
        return True
    # Check #ifndef TAG_DEFINED ... #define TAG_DEFINED
    if f"{tag}_DEFINED" in content:
        return True
    return False

# ---------------------------------------------------------------------------
# ensure_types_header_base  —  aggressive primitive cleanup + re-inject
# ---------------------------------------------------------------------------

def clean_conflicting_typedefs():
    """Remove conflicting typedefs for protected N64 OS primitive aliases."""
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
    """Ensure n64_types.h has a clean layout with primitives at the top."""
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

    # 1. Strip existing primitives block for clean re-injection
    content = re.sub(
        r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?",
        "", content)

    # 2. Wipe all loose primitive typedefs (prevents redefinition errors)
    primitive_list = ["u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
                      "f32", "f64", "n64_bool",
                      "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]
    for p in primitive_list:
        content = re.sub(rf"\btypedef\s+[^;]+\b{re.escape(p)}\s*;", "", content)

    # 3. Scrub structural stubs for primitive aliases
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(
            rf"(?:typedef\s+)?(?:struct\s+)?{re.escape(p)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(p)}\s*)?;?\n?",
            "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{re.escape(p)}(?:_s)?\s+{re.escape(p)}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{re.escape(p)}(?:_s)?\s*;\n?", "", content)

    # 4. Re-inject canonical primitives block after #pragma once
    content = content.replace("#pragma once", f"#pragma once\n{_CORE_PRIMITIVES}", 1)

    if content != original_content:
        write_file(TYPES_HEADER, content)
    return content

# ---------------------------------------------------------------------------
# Log scraper — self-healing: pulls unknown type errors from build logs
# ---------------------------------------------------------------------------

def _scrape_logs_into_categories(categories: dict) -> None:
    """Parse build logs and inject any new 'unknown type name' errors."""
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

    mt = categories.setdefault("missing_types", [])

    for log_file in set(log_candidates):
        if not os.path.exists(log_file):
            continue
        content = read_file(log_file)

        # Pattern with full filepath
        for m in re.finditer(
                r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+unknown type name '(\w+)'",
                content):
            filepath, tag = m.group(1), m.group(2)
            entry = (filepath, tag)
            if entry not in mt and not any(
                    isinstance(x, (list, tuple)) and len(x) >= 2 and x[1] == tag
                    for x in mt):
                mt.append(entry)

        # Fallback: no filepath
        for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            tag = m.group(1)
            if not any(
                    (isinstance(x, (list, tuple)) and len(x) >= 2 and x[1] == tag)
                    or x == tag
                    for x in mt):
                mt.append(tag)

        # Static declaration of 'X' follows non-static declaration → posix_conflict
        for m in re.finditer(
                r"(?m)^(/[^\s:]+\.c[^:]*):(?:\d+):(?:\d+):\s+error:\s+"
                r"static declaration of '(\w+)' follows non-static declaration",
                content):
            filepath, func = m.group(1), m.group(2)
            pc = categories.setdefault("posix_reserved_conflict", [])
            if (filepath, func) not in pc:
                pc.append((filepath, func))

# ---------------------------------------------------------------------------
# Main fix dispatcher
# ---------------------------------------------------------------------------

def apply_fixes(categories: dict) -> Tuple[int, set]:
    fixes       = 0
    fixed_files = set()

    # Pull any new errors from build logs before processing
    _scrape_logs_into_categories(categories)

    # Clean protected aliases, then rebuild header
    clean_conflicting_typedefs()
    types_content = ensure_types_header_base()

    # ------------------------------------------------------------------
    # Macro scrubber — remove 0-value stubs for now-known struct types
    # ------------------------------------------------------------------
    known_type_tags: Set[str] = set()
    for item in categories.get("missing_types", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            known_type_tags.add(item[1])
        elif isinstance(item, str):
            known_type_tags.add(item)
    for tag in categories.get("need_struct_body", []):
        if isinstance(tag, str):
            known_type_tags.add(tag)
    for item in categories.get("incomplete_sizeof", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            known_type_tags.add(item[1])
    for tag in categories.get("conflict_typedef", []):
        if isinstance(tag, str):
            known_type_tags.add(tag)
    # Also include all N64_OS_OPAQUE_TYPES so they get scrubbed on first encounter
    known_type_tags.update(N64_OS_OPAQUE_TYPES)
    known_type_tags.update(N64_STRUCT_BODIES.keys())

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

    # ------------------------------------------------------------------
    # Conflict typedef cleanup
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Missing members injection
    # ------------------------------------------------------------------
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
                if mn in an:
                    field = f"    unsigned char {mn}[128]; /* AUTO-ARRAY */\n"
                elif "ptr" in mn.lower() or "func" in mn.lower() or "cb" in mn.lower():
                    field = f"    void* {mn}; /* AUTO-POINTER */\n"
                else:
                    field = f"    long long int {mn};\n"
                return f"{match.group(1)}{body}{field}{match.group(3)}"
            return match.group(0)

        if re.search(pattern, types_content):
            new_types, n = re.subn(pattern, inject_member, types_content)
            if n > 0:
                write_file(TYPES_HEADER, new_types)
                fixes += 1
        else:
            mn = member_name
            if mn in array_names:
                field = f"unsigned char {mn}[128]; /* AUTO-ARRAY */"
            elif "ptr" in mn.lower() or "func" in mn.lower() or "cb" in mn.lower():
                field = f"void* {mn}; /* AUTO-POINTER */"
            else:
                field = f"long long int {mn};"
            types_content += (
                f"\nstruct {struct_name} {{\n    {field}\n"
                f"    long long int force_align[64];\n}};\n"
            )
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Variable redefinitions
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Missing types — opaque stubs, full bodies, or include injection
    # ------------------------------------------------------------------
    for item in sorted(categories.get("missing_types", []), key=str):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            filepath, tag = item[0], item[1]
        elif isinstance(item, str):
            filepath, tag = None, item
        else:
            continue

        if not isinstance(tag, str):
            continue

        types_content = read_file(TYPES_HEADER)

        # Skip primitives — already in the core block
        if tag in N64_PRIMITIVES:
            pass  # but still inject include below
        elif tag in N64_AUDIO_STATE_TYPES:
            if not _type_already_defined(tag, types_content):
                types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                write_file(TYPES_HEADER, types_content)
                fixes += 1
        elif tag in N64_STRUCT_BODIES:
            # Queue for full body injection
            categories.setdefault("need_struct_body", set()).add(tag)
        elif tag in N64_OS_OPAQUE_TYPES:
            # N64 OS types without a full body — use a sized opaque stub
            if not _type_already_defined(tag, types_content):
                types_content += "\n" + _opaque_stub(tag, size=64)
                write_file(TYPES_HEADER, types_content)
                fixes += 1
        else:
            # Unknown type — generic opaque stub
            struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
            if not _type_already_defined(tag, types_content):
                decl = (
                    f"struct {struct_tag} {{ long long int force_align[64]; }};\n"
                    f"typedef struct {struct_tag} {tag};\n"
                )
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content)
                fixed_files.add(TYPES_HEADER)
                fixes += 1

        # Ensure the source file includes n64_types.h
        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                fixed_files.add(filepath)
                fixes += 1

    # ------------------------------------------------------------------
    # Explicit audio state category
    # ------------------------------------------------------------------
    if categories.get("unknown_audio_state_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        for t in sorted(categories["unknown_audio_state_types"]):
            if not isinstance(t, str) or t not in N64_AUDIO_STATE_TYPES:
                continue
            if not _type_already_defined(t, types_content):
                types_content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
                added = True
        if added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Extraneous brace cleanup
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Conflicting implicit-type prototypes
    # ------------------------------------------------------------------
    for item in sorted(categories.get("conflicting_types", []), key=str):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        filepath, func = item[0], item[1]
        if not os.path.exists(filepath):
            continue
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

    # ------------------------------------------------------------------
    # Missing n64_types.h include
    # ------------------------------------------------------------------
    for item in sorted(categories.get("missing_n64_types", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        if 'n64_types.h"' not in content and '<n64_types.h>' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath)
            fixes += 1

    # ------------------------------------------------------------------
    # Actor pointer injection
    # ------------------------------------------------------------------
    for item in sorted(categories.get("actor_pointer", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath):
            continue
        content = original = read_file(filepath)
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # ------------------------------------------------------------------
    # Local struct forward declarations
    # ------------------------------------------------------------------
    if categories.get("local_struct_fwd"):
        file_to_types: dict = defaultdict(set)
        for item in categories["local_struct_fwd"]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                file_to_types[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
                continue
            content = read_file(filepath)
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content:
                    fwd_lines.append(fwd_decl)
            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n"
                write_file(filepath, injection + content)
                fixed_files.add(filepath)
                fixes += 1

    # ------------------------------------------------------------------
    # Typedef / struct redefinitions
    # ------------------------------------------------------------------
    fixd_files: set = set()
    for item in categories.get("typedef_redef", []):
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            fixd_files.add(item[0])
    for item in categories.get("struct_redef", []):
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            fixd_files.add(item[0])

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content  = read_file(filepath)
        original = content
        content  = strip_auto_preamble(content)

        tagged_body_re = re.compile(
            r'(?:typedef\s+)?struct\s+(\w+)\s*\{([^{}]*)\}\s*[^;]*;', re.DOTALL)
        tag_matches: dict = defaultdict(list)
        for m in tagged_body_re.finditer(content):
            tag_matches[m.group(1)].append(m)
        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]):
                    content = content[:m.start()] + content[m.end():]

        for item in categories.get("typedef_redef", []):
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            fp2, type1, type2 = item[0], item[1], item[2]
            if fp2 != filepath:
                continue
            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2):
                continue
            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            # Anonymous body → graft tag
            anon_pat = rf"typedef\s+struct\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_pat, content):
                _tt = target_tag
                def _anon_sub(m, tt=_tt):
                    return f"typedef struct {tt} {{{m.group(1)}}} {m.group(2)};"
                content, _ = re.subn(anon_pat, _anon_sub, content)
            else:
                # Named body with wrong alias tag
                bad_pat = rf"(?:typedef\s+)?struct\s+{re.escape(alias)}\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
                if re.search(bad_pat, content):
                    _tt2 = target_tag
                    def _bad_sub(m, tt=_tt2):
                        return f"typedef struct {tt} {{{m.group(1)}}} {m.group(2)};"
                    content, _ = re.subn(bad_pat, _bad_sub, content)
                else:
                    content, _ = re.subn(
                        r"\bstruct\s+" + re.escape(alias) + r"\b",
                        f"struct {target_tag}", content)

        for item in categories.get("struct_redef", []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            fp2, tag = item[0], item[1]
            if fp2 != filepath:
                continue
            content, _ = re.subn(
                rf'struct\s+{re.escape(tag)}\s*\{{[^}}]*\}}\s*;\n?', "", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # ------------------------------------------------------------------
    # Incomplete sizeof
    # ------------------------------------------------------------------
    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen: set = set()
        for item in categories["incomplete_sizeof"]:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            filepath, tag = item[0], item[1]
            if tag in seen:
                continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES:
                continue
            is_sdk = (tag.isupper()
                      or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_"))
                      or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Static / POSIX name conflicts
    # ------------------------------------------------------------------
    seen_static: set = set()
    for cat in ["static_conflict", "posix_conflict", "posix_reserved_conflict"]:
        for item in categories.get(cat, []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            filepath, func_name = item[0], item[1]
            key = (filepath, func_name)
            if key in seen_static:
                continue
            seen_static.add(key)
            if not func_name or not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
                continue
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

    # ------------------------------------------------------------------
    # Undeclared macros
    # ------------------------------------------------------------------
    if categories.get("undeclared_macros"):
        types_content = read_file(TYPES_HEADER)
        macros_added  = False
        for macro in sorted(categories["undeclared_macros"]):
            if not isinstance(macro, str):
                continue
            if macro in KNOWN_FUNCTION_MACROS:
                defn = KNOWN_FUNCTION_MACROS[macro]
                if defn not in types_content:
                    types_content += f"\n{defn}\n"
                    macros_added = True
            elif macro in KNOWN_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {KNOWN_MACROS[macro]}\n#endif\n"
                    macros_added = True
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Implicit function declarations → system headers
    # ------------------------------------------------------------------
    if categories.get("implicit_func"):
        math_funcs   = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        types_content  = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if not isinstance(func, str):
                continue
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

    # ------------------------------------------------------------------
    # Undefined linker symbols → stubs
    # ------------------------------------------------------------------
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
            if not isinstance(sym, str):
                continue
            if sym.startswith("_Z") or "vtable" in sym:
                continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    # ------------------------------------------------------------------
    # Audio-state opaque types
    # ------------------------------------------------------------------
    if categories.get("audio_states"):
        types_content = read_file(TYPES_HEADER)
        audio_added   = False
        for t in sorted(categories["audio_states"]):
            if not isinstance(t, str):
                continue
            if not _type_already_defined(t, types_content):
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Undeclared N64 platform types
    # ------------------------------------------------------------------
    if categories.get("undeclared_n64_types"):
        types_content = read_file(TYPES_HEADER)
        k_added = False
        for item in sorted(categories["undeclared_n64_types"], key=str):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                filepath, t = item[0], item[1]
            elif isinstance(item, str):
                filepath, t = None, item
            else:
                continue
            if not isinstance(t, str) or t in N64_PRIMITIVES:
                continue
            if t in N64_STRUCT_BODIES:
                categories.setdefault("need_struct_body", set()).add(t)
            elif not _type_already_defined(t, types_content):
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

    # ------------------------------------------------------------------
    # Undeclared GBI constants
    # ------------------------------------------------------------------
    if categories.get("undeclared_gbi"):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if not isinstance(ident, str):
                continue
            if ident in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {KNOWN_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                gbi_added = True
        if gbi_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Full struct bodies for known N64 types
    # ------------------------------------------------------------------
    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added  = False
        for tag in sorted(categories["need_struct_body"]):
            if not isinstance(tag, str):
                continue
            body = N64_STRUCT_BODIES.get(tag)
            if not body:
                # Fall back to opaque stub for OS types
                if tag in N64_OS_OPAQUE_TYPES and not _type_already_defined(tag, types_content):
                    types_content += "\n" + _opaque_stub(tag)
                    bodies_added = True
                continue
            if _type_already_defined(tag, types_content):
                continue
            if tag == "LookAt":
                types_content = re.sub(
                    r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__Light_t\s*;\n?", "", types_content)
                types_content = re.sub(
                    r"(?m)^typedef\s+struct\s*\{[^}]*\}\s*__LookAtDir\s*;\n?", "", types_content)
            if tag == "Mtx":
                types_content = re.sub(
                    r"(?m)^typedef\s+union\s*\{[^}]*\}\s*__Mtx_data\s*;\n?", "", types_content)
            # Strip any existing partial / opaque definition
            types_content = re.sub(
                rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(tag)}\s*)?;?\n?",
                "", types_content)
            types_content = re.sub(
                rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(tag)}\s*;\n?", "", types_content)
            types_content = re.sub(
                rf"typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;\n?", "", types_content)
            types_content = re.sub(
                rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
            # Also remove _DEFINED guard so we can inject fresh
            types_content = re.sub(
                rf"#ifndef {re.escape(tag)}_DEFINED[\s\S]*?#endif\n?", "", types_content)
            types_content += "\n" + body + "\n"
            bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # Local forward-only declarations
    # ------------------------------------------------------------------
    if categories.get("local_fwd_only"):
        file_to_types2: dict = defaultdict(set)
        for item in categories["local_fwd_only"]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                file_to_types2[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types2.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
                continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{[^}}]*\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
                fwd_decl = f"typedef struct {t}_s {t};"
                if re.search(body_pattern, content):
                    fwd = f"/* AUTO: forward decl for type defined below */\n{fwd_decl}\n"
                else:
                    fwd = f"/* AUTO: forward declarations */\n{fwd_decl}\n"
                if fwd_decl not in content:
                    content = fwd + content
                    changed = True
            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # ------------------------------------------------------------------
    # Missing global extern declarations
    # ------------------------------------------------------------------
    if categories.get("missing_globals"):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for item in sorted(categories["missing_globals"], key=str):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                _, glob = item[0], item[1]
            elif isinstance(item, str):
                glob = item
            else:
                continue
            if glob == "actor":
                continue
            if (f" {glob};" not in types_content and f"*{glob};" not in types_content
                    and f" {glob}[" not in types_content):
                decl = (f"extern void* {glob};" if glob.endswith(("_ptr", "_p"))
                        else f"extern long long int {glob};")
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    return fixes, fixed_files
