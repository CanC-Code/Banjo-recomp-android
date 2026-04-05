"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.
v86.0 — SDK primitive bootstrapping, POSIX handling, and robust struct injections.
"""

import os
import re
import subprocess
import time
from collections import defaultdict

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=1", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError",
    "-Pandroid.ndk.cmakeArgs=-k 0",
]
LOG_FILE        = "Android/full_build_log.txt"
FAILED_LOG_FILE = "Android/failed_files.log"
TYPES_HEADER    = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE      = "Android/app/src/main/cpp/ultra/n64_stubs.c"

MAX_STALL = 5

# Matches up to 4 levels of nested braces securely
BRACE_MATCH = r"[^{}]*"
for _ in range(4):
    BRACE_MATCH = r"(?:[^{}]|\{" + BRACE_MATCH + r"\})*"

N64_IDENT_TYPES = {
    "OSIntMask", "OSMesgQueue", "OSMesg", "OSThread", "OSTimer", "OSTime",
    "OSEvent", "OSPri", "OSId", "OSTask", "OSTask_t", "CPUState",
}

N64_STRUCT_BODIES = {
    "Mtx": """\
/* N64 Mtx: fixed-point 16.16 matrix */
typedef union {
    s32  i[4][4];    
    f32  f[4][4];    
} __Mtx_data;
typedef struct Mtx_s {
    s16  m[4][4];    
    u16  h[4][4];    
} Mtx;
""",

    "LookAt": """\
/* N64 LookAt */
typedef struct {
    u8 col[3];
    u8 pad1;
    u8 colc[3];
    u8 pad2;
    s8 dir[3];
    u8 pad3;
} __Light_t;
typedef struct {
    __Light_t l;
} __LookAtDir;
typedef struct LookAt_s {
    __LookAtDir l[2];
} LookAt;
""",

    "OSPfs": """\
/* N64 OSPfs stub */
typedef struct OSPfs_s {
    u32  status;
    u32  fileSize;
    u32  initFlag;
    u32  reserved[29];   
} OSPfs;
""",
}

KNOWN_MACROS = {
    "ADPCMFSIZE": "9", "ADPCMVSIZE": "8", "UNITY_PITCH": "0x8000", "MAX_RATIO": "0x8000000",
    "OS_IM_NONE": "0x0001", "OS_IM_SW1": "0x0005", "OS_IM_SW2": "0x0009", "OS_IM_CART": "0x0411",
    "OS_IM_PRENMI": "0x0021", "OS_IM_RDBWRITE": "0x0041", "OS_IM_RDBREAD": "0x0081",
    "OS_IM_COUNTER": "0x0101", "OS_IM_CPU": "0x0201", "OS_IM_SP": "0x0441", "OS_IM_SI": "0x0811",
    "OS_IM_AI": "0x1001", "OS_IM_VI": "0x2001", "OS_IM_PI": "0x4001", "OS_IM_DP": "0x8001",
    "OS_IM_ALL": "0xFF01", "OS_TV_NTSC": "0", "OS_TV_PAL": "1", "OS_TV_MPAL": "2",
    "PFS_ERR_ID_FATAL": "1", "PFS_ERR_DEVICE": "11", "PFS_ERR_CHECKSUM": "5",
    "PFS_ERR_LONGFAIL": "6", "PFS_ERR_SHORT_DIR": "10", "PFS_ERR_INVALID": "12",
    "PFS_ERR_BROKEN": "13", "PFS_ERR_NOPACK": "14", "G_ZBUFFER": "0x00000001",
    "G_SHADE": "0x00000004", "G_CULL_FRONT": "0x00000200", "G_CULL_BACK": "0x00000400",
    "G_CULL_BOTH": "0x00000600", "G_FOG": "0x00010000", "G_LIGHTING": "0x00020000",
    "G_TEXTURE_GEN": "0x00040000", "G_TEXTURE_GEN_LINEAR": "0x00080000", "G_LOD": "0x00100000",
    "G_SHADING_SMOOTH": "0x00200000", "G_CLIPPING": "0x00800000", "G_CYC_1CYCLE": "(0<<20)",
    "G_CYC_2CYCLE": "(1<<20)", "G_CYC_COPY": "(2<<20)", "G_CYC_FILL": "(3<<20)",
    "G_PM_NPRIMITIVE": "(0<<23)", "G_PM_1PRIMITIVE": "(1<<23)", "G_AC_NONE": "(0<<0)",
    "G_AC_THRESHOLD": "(1<<0)", "G_AC_DITHER": "(3<<0)", "G_CD_MAGICSQ": "(0<<6)",
    "G_CD_BAYER": "(1<<6)", "G_CD_NOISE": "(2<<6)", "G_CD_DISABLE": "(3<<6)",
    "G_SC_NON_INTERLACE": "0", "G_SC_ODD_INTERLACE": "3", "G_SC_EVEN_INTERLACE": "1",
    "G_TC_CONV": "(0<<9)", "G_TC_FILTCONV": "(5<<9)", "G_TC_FILT": "(6<<9)",
    "G_IM_FMT_RGBA": "0", "G_IM_FMT_YUV": "1", "G_IM_FMT_CI": "2", "G_IM_FMT_IA": "3",
    "G_IM_FMT_I": "4", "G_IM_SIZ_4b": "0", "G_IM_SIZ_8b": "1", "G_IM_SIZ_16b": "2",
    "G_IM_SIZ_32b": "3", "G_RM_NOOP": "0", "G_RM_NOOP2": "0", "G_RM_OPA_SURF": "0x0f0a4000",
    "G_RM_OPA_SURF2": "0x0f0a4000", "G_RM_AA_OPA_SURF": "0x0f184000", "G_RM_AA_OPA_SURF2": "0x0f184000",
    "G_RM_AA_XLU_SURF": "0x00194248", "G_RM_AA_XLU_SURF2": "0x00194248",
}

KNOWN_FUNCTION_MACROS = {
    "FTOFRAC8": "#define FTOFRAC8(x) ((s32)((x) * 127.0f) & 0xFF)",
    "OS_K0_TO_PHYSICAL": "#define OS_K0_TO_PHYSICAL(x) ((u32)(x) & 0x1FFFFFFF)",
    "OS_PHYSICAL_TO_K0": "#define OS_PHYSICAL_TO_K0(x) ((void *)((u32)(x) | 0x80000000))",
    "OS_PHYSICAL_TO_K1": "#define OS_PHYSICAL_TO_K1(x) ((void *)((u32)(x) | 0xA0000000))",
}

KNOWN_GLOBAL_TYPES = {
    "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx", "LookAt", "RESAMPLE_STATE", "ENVMIX_STATE", "POLEF_STATE",
    "OSContPad", "OSContStatus", "OSTimer", "OSTime", "OSMesg", "OSEvent", "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
    "OSIntMask", "OSPfs", "OSPiHandle", "Actor", "ActorMarker",
    "s8", "u8", "s16", "u16", "s32", "u32", "s64", "u64", "f32", "f64", "n64_bool", "OSPri", "OSId",
}

# N64 audio DSP state types
N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
    "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
    "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE", "ALVoiceState"
}

# POSIX / libc reserved function names
POSIX_RESERVED_NAMES = {
    "close", "open", "read", "write", "send", "recv",
    "connect", "accept", "bind", "listen", "select",
    "poll", "dup", "dup2", "fork", "exec", "exit",
    "stat", "fstat", "lstat", "access", "unlink", "rename",
    "mkdir", "rmdir", "chdir", "getcwd", "getpid", "getppid",
    "getuid", "getgid", "signal", "raise", "kill",
    "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf",
    "time", "clock", "sleep", "usleep", "malloc", "calloc", "realloc", "free",
    "memcpy", "memset", "memmove", "memcmp", "strlen", "strcpy", "strncpy",
    "strcmp", "strncmp", "strcat", "strncat", "strchr", "strrchr", "strstr",
    "atoi", "atol", "atof", "strtol", "strtod",
    "abs", "labs", "fabs", "sqrt", "pow", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "rand", "srand",
}


# ─── Utilities ────────────────────────────────────────────────────────────────

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def run_build():
    print("\n🚀 Starting Build Cycle...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w") as log:
        try:
            process = subprocess.Popen(
                GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in process.stdout:
                clean_line = strip_ansi(line)
                log.write(clean_line)
                print(clean_line, end="")
            process.wait()
            return process.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}")
            return False

def extract_incomplete_type(line):
    m = re.search(r"incomplete (?:element )?type '(?:struct\s+)?([^']+)'", line)
    if m: return m.group(1)
    m = re.search(r"\(aka '(?:struct\s+)?([^']+)'\)", line)
    return m.group(1) if m else None

def source_path(path):
    if not path: return None
    p = path.replace("C/C++: ", "").strip()
    if "/Banjo-recomp-android/Banjo-recomp-android/" in p:
        p = p.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
    return os.path.normpath(p)

def is_sdk_or_ndk_path(fp):
    if not fp: return True
    normalized = fp.replace("\\", "/")
    return "/usr/" in normalized or "ndk" in normalized.lower()

def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f: return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f: f.write(content)

def is_defined_locally(filepath, tag):
    if not filepath or not os.path.exists(filepath): return False
    c = read_file(filepath)
    pattern1 = rf"typedef\s+struct[^{{]*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(tag)}\b[^;]*;"
    pattern2 = rf"struct\s+{re.escape(tag)}\s*\{{({BRACE_MATCH})\}}"
    return bool(re.search(pattern1, c) or re.search(pattern2, c))

def strip_auto_preamble(content):
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

def ensure_types_header_base():
    """Ensure n64_types.h exists, injects stdint & primitives, and bootstraps audio states."""
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    # Proactively inject basic N64 primitives and stdint.h so struct additions parse successfully!
    required_types = [
        ("#include <stdint.h>", "#include <stdint.h>"),
        ("typedef uint32_t u32;", "typedef uint8_t u8;\ntypedef int8_t s8;\ntypedef uint16_t u16;\ntypedef int16_t s16;\ntypedef uint32_t u32;\ntypedef int32_t s32;\ntypedef uint64_t u64;\ntypedef int64_t s64;\ntypedef float f32;\ntypedef double f64;")
    ]
    
    changed = False
    for check, injection in required_types:
        if check not in content:
            content = content.replace("#pragma once", f"#pragma once\n{injection}\n")
            changed = True
            
    # Proactively inject audio states
    for t in N64_AUDIO_STATE_TYPES:
        if f"typedef struct {t}" not in content and f"}} {t};" not in content:
            content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
            changed = True
            
    if changed or not os.path.exists(TYPES_HEADER):
        write_file(TYPES_HEADER, content)
        
    return content

def canonical_tag(name):
    if len(name) > 1 and name[0].islower() and name[1].isupper():
        base = name[1].lower() + name[2:]
        return base + "_s"
    return name + "_s"

def remove_conflicting_fwd_decl(content, alias):
    expected_tag = canonical_tag(alias)
    pat = re.compile(
        r'/\* AUTO: forward decl[^\n]*/\n'
        r'typedef\s+struct\s+' + re.escape(expected_tag) + r'\s+' + re.escape(alias) + r'\s*;\n?'
    )
    new_content, n = pat.subn("", content)
    if n == 0:
        pat2 = re.compile(r'typedef\s+struct\s+' + re.escape(expected_tag) + r'\s+' + re.escape(alias) + r'\s*;\n?')
        new_content, n = pat2.subn("", content)
    return new_content, n > 0

def fix_body_tag(content, alias):
    expected = canonical_tag(alias)
    pat = re.compile(
        r'(typedef\s+struct\s+)(\w+)(\s*\{[^{}]*\}\s*(?:[^;]*\b)' + re.escape(alias) + r'\b[^;]*;)',
        re.DOTALL
    )
    changed = False
    def _sub(m):
        nonlocal changed
        if m.group(2) == expected: return m.group(0)
        changed = True
        return m.group(1) + expected + m.group(3)
    new_content = pat.sub(_sub, content)
    return new_content, changed

def _rename_posix_static(content, func_name, filepath):
    prefix    = os.path.basename(filepath).split('.')[0]
    new_name  = f"n64_{prefix}_{func_name}"
    define    = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True


# ─── Failed-file log ──────────────────────────────────────────────────────────

def generate_failed_log(log_data):
    file_errors = defaultdict(set)
    loose_errors = set()
    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    for line in log_data.split('\n'):
        if ("error:" not in line and "undefined reference" not in line and "undefined symbol" not in line): continue
        if "too many errors emitted" in line: continue
        m_file = re.search(file_regex, line)
        fp = source_path(m_file.group(1) if m_file else None)
        m_err = re.search(r"error:\s*(.*)", line)
        msg = m_err.group(1).strip() if m_err else line.strip()
        if fp and not is_sdk_or_ndk_path(fp): file_errors[fp].add(msg)
        else: loose_errors.add(msg)

    out = ["=" * 70, "FAILED FILES LOG", "=" * 70, ""]
    for fp in sorted(file_errors):
        out.append(f"FILE: {fp}")
        for err in sorted(file_errors[fp]): out.append(f"  • {err}")
        out.append("")
    if loose_errors:
        out.append("LINKER / UNATTRIBUTED ERRORS:")
        for err in sorted(loose_errors): out.append(f"  • {err}")
        out.append("")

    with open(FAILED_LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"\n📋 FAILED FILES SUMMARY  →  {FAILED_LOG_FILE}")
    return set(file_errors.keys())

def generate_error_summary(log_data):
    errors = set()
    for line in log_data.split('\n'):
        if "error:" in line and "too many errors emitted" not in line:
            m = re.search(r"error:\s*(.*)", line)
            if m: errors.add(m.group(1).strip())
    print("\n📋 CONDENSED ERROR SUMMARY")
    for e in sorted(errors): print(f"- {e}")
    print("\n")


# ─── Error classification ─────────────────────────────────────────────────────

def classify_errors(log_data):
    categories = {
        "missing_n64_types":       set(),
        "actor_pointer":           set(),
        "local_struct_fwd":        [],
        "local_fwd_only":          [],
        "typedef_redef":           [],
        "struct_redef":            [],
        "static_conflict":         [],
        "posix_reserved_conflict": [],
        "conflicting_types":       set(),
        "incomplete_sizeof":       [],
        "need_struct_body":        set(),
        "need_mtx_body":           False,
        "undeclared_macros":       set(),
        "undeclared_gbi":          set(),
        "undeclared_n64_types":    set(),
        "missing_types":           set(), # Flat set of tuples: (filepath, type_name)
        "missing_globals":         set(), # Flat set of tuples: (filepath, ident)
        "implicit_func":           set(),
        "undefined_symbols":       set(),
        "audio_states":            set(), # Flat set of tuples: (filepath, type_name)
        "extraneous_brace":        False,
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    for line in log_data.split('\n'):
        if "extraneous closing brace" in line:
            categories["extraneous_brace"] = True

        if ("error:" not in line and "undefined reference" not in line and "undefined symbol" not in line and "note:" not in line):
            continue

        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)
        if is_sdk_or_ndk_path(filepath): filepath = None

        m_redef        = re.search(r"typedef redefinition with different types \('([^']+)'(?:.*?)vs '([^']+)'(?:.*?)\)", line)
        m_struct_redef = re.search(r"redefinition of '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_no_member    = re.search(r"no member named '([^']+)' in '(?:struct )?([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_static       = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown_type = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_ident        = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit     = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_ref    = re.search(r"undefined reference to `([^']+)'", line)
        m_undef_sym    = re.search(r"undefined symbol: (.*)", line)
        m_incomplete   = re.search(r"incomplete definition of type '(?:struct\s+)?([^']+)'", line)
        m_tentative    = re.search(r"tentative definition has type '([^']+)' \(aka '(?:struct\s+)?([^']+)'\) that is never completed", line)
        m_conflict     = re.search(r"error: conflicting types for '([^']+)'", line)

        if m_conflict and filepath:
            categories["conflicting_types"].add((filepath, m_conflict.group(1)))

        if m_no_member:
            tag = m_no_member.group(2)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in ("Mtx", "Mtx_s"):
                categories["need_mtx_body"] = True
            if base_tag in N64_STRUCT_BODIES:
                categories["need_struct_body"].add(base_tag)

        if m_incomplete and filepath:
            tag = m_incomplete.group(1)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES: categories["need_struct_body"].add(base_tag)
            else: categories["incomplete_sizeof"].append((filepath, tag))

        if m_tentative and filepath:
            tag = m_tentative.group(2)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES: categories["need_struct_body"].add(base_tag)
            else: categories["incomplete_sizeof"].append((filepath, tag))

        if m_redef and filepath: categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))
        if m_struct_redef and filepath: categories["struct_redef"].append((filepath, m_struct_redef.group(1)))

        if m_unknown_type and filepath:
            type_name = m_unknown_type.group(1)

            if type_name in N64_STRUCT_BODIES:
                categories["need_struct_body"].add(type_name)

            if type_name in N64_AUDIO_STATE_TYPES:
                categories["audio_states"].add((filepath, type_name)) 
            else:
                if is_defined_locally(filepath, type_name):
                    categories["local_fwd_only"].append((filepath, type_name))
                elif type_name.istitle() or re.match(r'^[A-Z][A-Za-z0-9_]*$', type_name):
                    categories["missing_types"].add((filepath, type_name))
                else:
                    categories["local_fwd_only"].append((filepath, type_name))

        if m_ident:
            ident = m_ident.group(1)
            if ident in N64_IDENT_TYPES: categories["undeclared_n64_types"].add(ident)
            elif ident.startswith("G_") or ident.startswith("g_"): categories["undeclared_gbi"].add(ident)
            elif ident in KNOWN_MACROS or ident in KNOWN_FUNCTION_MACROS or ident.isupper():
                categories["undeclared_macros"].add(ident)
            elif ident.istitle() or re.match(r'^[A-Z][A-Za-z0-9_]*$', ident):
                if filepath and is_defined_locally(filepath, ident): categories["local_fwd_only"].append((filepath, ident))
                else:
                    if filepath: categories["missing_types"].add((filepath, ident))
            else:
                if filepath: categories["missing_globals"].add((filepath, ident))

        if m_undef_ref: categories["undefined_symbols"].add(m_undef_ref.group(1).strip())
        if m_undef_sym: categories["undefined_symbols"].add(m_undef_sym.group(1).replace("'", "").strip())
        if m_implicit: categories["implicit_func"].add(m_implicit.group(1))
        
        if m_static and filepath: 
            func_name = m_static.group(1)
            if func_name in POSIX_RESERVED_NAMES:
                categories["posix_reserved_conflict"].append((filepath, func_name))
            else:
                categories["static_conflict"].append((filepath, func_name))

        if ("invalid application of 'sizeof'" in line or "arithmetic on a pointer to an incomplete type" in line or "array has incomplete element type" in line) and filepath:
            inc_type = extract_incomplete_type(line)
            if inc_type:
                base_tag = inc_type[:-2] if inc_type.endswith("_s") else inc_type
                if base_tag in N64_STRUCT_BODIES: categories["need_struct_body"].add(base_tag)
                else: categories["incomplete_sizeof"].append((filepath, inc_type))

        if filepath and os.path.exists(filepath):
            if "error:" in line: categories["missing_n64_types"].add(filepath)

    seen_local_fwd = set()
    new_local_fwd = []
    for filepath, type_name in categories["local_fwd_only"]:
        base_type = type_name[:-2] if type_name.endswith("_s") else type_name
        if base_type in KNOWN_GLOBAL_TYPES or type_name in KNOWN_GLOBAL_TYPES:
            categories["missing_n64_types"].add(filepath)
        else:
            key = (filepath, type_name)
            if key not in seen_local_fwd:
                seen_local_fwd.add(key)
                new_local_fwd.append((filepath, type_name))
    categories["local_fwd_only"] = new_local_fwd

    # Ensure known global types caught in missing_types or globals trigger n64_types.h inclusion
    missing_types_clean = set()
    for fp, type_name in categories["missing_types"]:
        if type_name in KNOWN_GLOBAL_TYPES:
            categories["missing_n64_types"].add(fp)
        else:
            missing_types_clean.add((fp, type_name))
    categories["missing_types"] = missing_types_clean

    missing_globals_clean = set()
    for fp, ident in categories["missing_globals"]:
        if ident in KNOWN_GLOBAL_TYPES:
            categories["missing_n64_types"].add(fp)
        else:
            missing_globals_clean.add((fp, ident))
    categories["missing_globals"] = missing_globals_clean

    return categories


# ─── Main Dispatcher ──────────────────────────────────────────────────────────

def apply_fixes():
    if not os.path.exists(LOG_FILE): return 0, set()

    log_data = read_file(LOG_FILE)
    categories = classify_errors(log_data)
    failed_files = generate_failed_log(log_data)

    fixes = 0
    fixed_files = set()

    types_content = ensure_types_header_base()

    if categories["extraneous_brace"]:
        original = types_content
        types_content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", types_content)
        types_content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    for filepath, func in sorted(categories["conflicting_types"]):
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
                if includes:
                    idx = includes[-1].end()
                    content = content[:idx] + injection + content[idx:]
                else:
                    content = injection + content
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    for filepath in sorted(categories["missing_n64_types"]):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath)
            fixes += 1

    for filepath in sorted(categories["actor_pointer"]):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        original = content
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories["local_struct_fwd"]:
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_struct_fwd"]: file_to_types[filepath].add(type_name)
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

    # ── FIX D: Typedef / Struct Redefinition ────────────────────────────
    fixd_files = set()
    for filepath, _, _ in categories["typedef_redef"]: fixd_files.add(filepath)
    for filepath, _ in categories["struct_redef"]: fixd_files.add(filepath)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        original = content

        content = strip_auto_preamble(content)

        tagged_body_re = re.compile(
            rf'(?:typedef\s+)?struct\s+(\w+)\s*\{{({BRACE_MATCH})\}}\s*[^;]*;',
            re.DOTALL
        )
        tag_matches = defaultdict(list)
        for m in tagged_body_re.finditer(content): tag_matches[m.group(1)].append(m)
        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]): content = content[:m.start()] + content[m.end():]

        for fp2, type1, type2 in categories["typedef_redef"]:
            if fp2 != filepath: continue
            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2): continue
            
            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            if alias in KNOWN_GLOBAL_TYPES or target_tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    rf'(?:typedef\s+)?struct\s+{re.escape(target_tag)}?\s*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(alias)}\b[^;]*;\n?',
                    "", content
                )
                content = re.sub(rf'typedef\s+struct\s+{re.escape(target_tag)}\s+{re.escape(alias)}\s*;\n?', '', content)
                continue
            
            # Complex Alias Preserving Regex
            anon_body_pattern = rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_body_pattern, content):
                def _anon_sub(m, tt=target_tag):
                    body_inner = m.group(1)
                    declarator = m.group(2)
                    return f"typedef struct {tt} {{{body_inner}}} {declarator};"
                content, _ = re.subn(anon_body_pattern, _anon_sub, content)
            else:
                content, _ = re.subn(
                    r"\bstruct\s+" + re.escape(alias) + r"\b",
                    f"struct {target_tag}", content
                )

        for fp2, tag in categories["struct_redef"]:
            if fp2 != filepath: continue
            if tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    rf'struct\s+{re.escape(tag)}\s*\{{({BRACE_MATCH})\}}\s*;\n?',
                    "", content
                )

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories["incomplete_sizeof"]:
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen = set()
        for filepath, tag in categories["incomplete_sizeof"]:
            if tag in seen: continue
            seen.add(tag)
            
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES: continue
                
            is_sdk = (tag.isupper() or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_")) or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── Unified Static-name conflicts (POSIX handled correctly) ─────────
    seen_static = set()
    for cat in ["static_conflict", "posix_reserved_conflict"]:
        for filepath, func_name in categories.get(cat, []):
            key = (filepath, func_name)
            if key in seen_static: continue
            seen_static.add(key)
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            
            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath); fixes += 1
                continue

            prefix = os.path.basename(filepath).split('.')[0]
            macro_fix = (f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n")
            if macro_fix not in content:
                anchor = '#include "ultra/n64_types.h"'
                content = (content.replace(anchor, anchor + macro_fix) if anchor in content else macro_fix + content)
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    if categories["undeclared_macros"]:
        types_content = read_file(TYPES_HEADER)
        macros_added = False
        for macro in sorted(categories["undeclared_macros"]):
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

    if categories["implicit_func"]:
        math_funcs   = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        types_content = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs:   header = "<stdlib.h>"
            else:                        continue
            if f"#include {header}" not in types_content:
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["undefined_symbols"]:
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace("add_library(", "add_library(\n        ultra/n64_stubs.c")
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added = False
        for sym in sorted(categories["undefined_symbols"]):
            if sym.startswith("_Z") or "vtable" in sym: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    # ── Missing Type / Audio Type Handlers ───────
    for cat in ["audio_states", "missing_types"]:
        if categories.get(cat):
            types_content = read_file(TYPES_HEADER)
            types_added   = False
            
            for filepath, tag in sorted(categories[cat]):
                if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                    c = read_file(filepath)
                    if 'include "ultra/n64_types.h"' not in c:
                        write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                        fixed_files.add(filepath); fixes += 1

                if tag in N64_AUDIO_STATE_TYPES:
                    if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                        types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                        types_added = True
                    continue

                base_tag = tag[:-2] if tag.endswith("_s") else tag
                if base_tag in N64_STRUCT_BODIES or tag in KNOWN_GLOBAL_TYPES:
                    if base_tag in N64_STRUCT_BODIES:
                        categories["need_struct_body"].add(base_tag)
                    continue
                        
                if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                    types_content += f"\ntypedef struct {tag} {{ int dummy_data[128]; }} {tag};\n"
                    types_added = True
                    
            if types_added:
                write_file(TYPES_HEADER, types_content); fixes += 1

    if categories["undeclared_n64_types"]:
        types_content = read_file(TYPES_HEADER)
        k_added = False
        if "OSIntMask" in categories["undeclared_n64_types"]:
            if "OSIntMask" not in types_content:
                types_content += "\n/* N64 interrupt mask type */\ntypedef u32 OSIntMask;\n"
                k_added = True
            for macro, val in sorted(KNOWN_MACROS.items()):
                if macro.startswith("OS_IM_") and f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {val}\n#endif\n"
                    k_added = True
        if k_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1
        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs)
                fixes += 1

    if categories["undeclared_gbi"]:
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if ident in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {KNOWN_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in KNOWN_MACROS:
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                    gbi_added = True
        if gbi_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["need_mtx_body"]:
        types_content = read_file(TYPES_HEADER)
        if "i[4][4]" not in types_content and "m[4][4]" not in types_content:
            types_content = re.sub(rf"(?:typedef\s+)?struct\s+Mtx(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:Mtx\s*)?;?\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*Mtx\s*;\n?", "", types_content)
            types_content = re.sub(r"typedef\s+struct\s+Mtx(?:_s)?\s+Mtx\s*;\n?", "", types_content)
            types_content = re.sub(r"struct\s+Mtx(?:_s)?\s*;\n?", "", types_content)
            
            types_content += "\n" + N64_STRUCT_BODIES["Mtx"]
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["need_struct_body"]:
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(categories["need_struct_body"]):
            if tag == "Mtx": continue  
            body = N64_STRUCT_BODIES.get(tag)
            
            if body:
                # Dynamically set a unique check string for safe injection
                if tag == "LookAt": check_str = "__Light_t"
                elif tag == "OSPfs": check_str = "fileSize;"
                elif tag == "OSContStatus": check_str = "errno;"
                elif tag == "OSContPad": check_str = "stick_x;"
                elif tag == "OSPiHandle": check_str = "pageSize;"
                else: check_str = body.split('\n')[2].strip() 
                
                if check_str not in types_content:
                    types_content = re.sub(rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:{re.escape(tag)}\s*)?;?\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*{re.escape(tag)}\s*;\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;\n?", "", types_content)
                    types_content = re.sub(rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
                    types_content += "\n" + body
                    bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["local_fwd_only"]:
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_fwd_only"]: file_to_types[filepath].add(type_name)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
                if re.search(body_pattern, content):
                    fwd = f"/* AUTO: forward decl for type defined below */\ntypedef struct {t}_s {t};\n"
                    if f"typedef struct {t}_s {t};" not in content:
                        content = fwd + content
                        changed = True
                else:
                    fwd = f"/* AUTO: forward declarations */\ntypedef struct {t}_s {t};\n"
                    if f"typedef struct {t}_s {t};" not in content:
                        content = fwd + content
                        changed = True
            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    if categories["missing_globals"]:
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for filepath, glob in sorted(categories["missing_globals"]):
            if glob == "actor": continue
            if f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content:
                decl = f"extern void* {glob};" if glob.endswith(("_ptr", "_p")) else f"extern long long int {glob};"
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if fixes == 0:
        generate_error_summary(log_data)
    else:
        print(f"\n  ✅ Applied {fixes} fix(es) across {len(fixed_files)} source file(s) this cycle.")

    return fixes, failed_files


def main():
    stall_count = 0

    for i in range(1, 200):
        print(f"\n{'='*40}\n--- Cycle {i} ---\n{'='*40}")

        if run_build():
            print("\n✅ Build Successful!")
            if os.path.exists(FAILED_LOG_FILE): os.remove(FAILED_LOG_FILE)
            return

        fixes, failed_files = apply_fixes()

        if fixes == 0:
            stall_count += 1
            print(f"\n⚠️  No fixable patterns this cycle. Stall count: {stall_count}/{MAX_STALL}")
            if failed_files: print(f"   {len(failed_files)} file(s) still failing — see {FAILED_LOG_FILE}")
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted after {MAX_STALL} consecutive stall cycles.")
                break
        else:
            stall_count = 0

        time.sleep(1)


if __name__ == "__main__":
    main()
