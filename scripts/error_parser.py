import os
import re
from collections import defaultdict

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

def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f: return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f: f.write(content)

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

def is_defined_locally(filepath, tag):
    if not filepath or not os.path.exists(filepath): return False
    c = read_file(filepath)
    pattern1 = rf"typedef\s+struct[^{{]*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(tag)}\b[^;]*;"
    pattern2 = rf"struct\s+{re.escape(tag)}\s*\{{({BRACE_MATCH})\}}"
    return bool(re.search(pattern1, c) or re.search(pattern2, c))

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
        "missing_types":           set(), 
        "missing_globals":         set(), 
        "implicit_func":           set(),
        "undefined_symbols":       set(),
        "audio_states":            set(), 
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
            if ident in N64_IDENT_TYPES: 
                categories["undeclared_n64_types"].add(ident)
            elif ident.startswith("G_") or ident.startswith("g_"): 
                categories["undeclared_gbi"].add(ident)
            elif ident in KNOWN_MACROS or ident in KNOWN_FUNCTION_MACROS:
                categories["undeclared_macros"].add(ident)
            # BUG FIX: Intercept known audio states / globals so they don't get cast as macros
            elif ident in N64_AUDIO_STATE_TYPES:
                if filepath: categories["audio_states"].add((filepath, ident))
            elif ident in KNOWN_GLOBAL_TYPES:
                if filepath: categories["missing_globals"].add((filepath, ident))
            elif ident.isupper():
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

def generate_failed_log(log_data, failed_log_file):
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

    with open(failed_log_file, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"\n📋 FAILED FILES SUMMARY  →  {failed_log_file}")
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
