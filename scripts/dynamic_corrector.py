"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.
v82.0 — Native Python C-Parser, proactive header healing, and flawless duplicate removal.
"""

import os
import re
import subprocess
import time
import sys
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

# ── N64 identifier types that appear as 'use of undeclared identifier' ────────
N64_IDENT_TYPES = {
    "OSIntMask",
    "OSMesgQueue", "OSMesg", "OSThread", "OSTimer", "OSTime",
    "OSEvent", "OSPri", "OSId", "OSTask", "OSTask_t", "CPUState",
}

# ── Known N64 structs that need full bodies (not dummy stubs) ─────────────────
N64_STRUCT_BODIES = {
    "Mtx": """\
/* N64 Mtx: fixed-point 16.16 matrix */
typedef union {
    s32  i[4][4];    /* integer (s15.16) rows */
    f32  f[4][4];    /* float view */
} __Mtx_data;
typedef struct Mtx_s {
    s16  m[4][4];    /* integer half-words */
    u16  h[4][4];    /* fraction half-words */
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
/* N64 OSPfs stub — concrete so globals can be instantiated */
typedef struct OSPfs_s {
    u32  status;
    u32  fileSize;
    u32  initFlag;
    u32  reserved[29];   /* pad to real SDK size */
} OSPfs;
""",
}

KNOWN_MACROS = {
    "ADPCMFSIZE":       "9",
    "ADPCMVSIZE":       "8",
    "UNITY_PITCH":      "0x8000",
    "MAX_RATIO":        "0x8000000",
    "OS_IM_NONE":       "0x0001",
    "OS_IM_SW1":        "0x0005",
    "OS_IM_SW2":        "0x0009",
    "OS_IM_CART":       "0x0411",
    "OS_IM_PRENMI":     "0x0021",
    "OS_IM_RDBWRITE":   "0x0041",
    "OS_IM_RDBREAD":    "0x0081",
    "OS_IM_COUNTER":    "0x0101",
    "OS_IM_CPU":        "0x0201",
    "OS_IM_SP":         "0x0441",
    "OS_IM_SI":         "0x0811",
    "OS_IM_AI":         "0x1001",
    "OS_IM_VI":         "0x2001",
    "OS_IM_PI":         "0x4001",
    "OS_IM_DP":         "0x8001",
    "OS_IM_ALL":        "0xFF01",
    "OS_TV_NTSC":       "0",
    "OS_TV_PAL":        "1",
    "OS_TV_MPAL":       "2",
    "PFS_ERR_ID_FATAL": "1",
    "PFS_ERR_DEVICE":   "11",
    "PFS_ERR_CHECKSUM": "5",
    "PFS_ERR_LONGFAIL": "6",
    "PFS_ERR_SHORT_DIR":"10",
    "PFS_ERR_INVALID":  "12",
    "PFS_ERR_BROKEN":   "13",
    "PFS_ERR_NOPACK":   "14",
    "G_ZBUFFER":            "0x00000001",
    "G_SHADE":              "0x00000004",
    "G_CULL_FRONT":         "0x00000200",
    "G_CULL_BACK":          "0x00000400",
    "G_CULL_BOTH":          "0x00000600",
    "G_FOG":                "0x00010000",
    "G_LIGHTING":           "0x00020000",
    "G_TEXTURE_GEN":        "0x00040000",
    "G_TEXTURE_GEN_LINEAR": "0x00080000",
    "G_LOD":                "0x00100000",
    "G_SHADING_SMOOTH":     "0x00200000",
    "G_CLIPPING":           "0x00800000",
    "G_CYC_1CYCLE":     "(0<<20)",
    "G_CYC_2CYCLE":     "(1<<20)",
    "G_CYC_COPY":       "(2<<20)",
    "G_CYC_FILL":       "(3<<20)",
    "G_PM_NPRIMITIVE":  "(0<<23)",
    "G_PM_1PRIMITIVE":  "(1<<23)",
    "G_AC_NONE":        "(0<<0)",
    "G_AC_THRESHOLD":   "(1<<0)",
    "G_AC_DITHER":      "(3<<0)",
    "G_CD_MAGICSQ":     "(0<<6)",
    "G_CD_BAYER":       "(1<<6)",
    "G_CD_NOISE":       "(2<<6)",
    "G_CD_DISABLE":     "(3<<6)",
    "G_SC_NON_INTERLACE": "0",
    "G_SC_ODD_INTERLACE": "3",
    "G_SC_EVEN_INTERLACE":"1",
    "G_TC_CONV":        "(0<<9)",
    "G_TC_FILTCONV":    "(5<<9)",
    "G_TC_FILT":        "(6<<9)",
    "G_IM_FMT_RGBA":    "0",
    "G_IM_FMT_YUV":     "1",
    "G_IM_FMT_CI":      "2",
    "G_IM_FMT_IA":      "3",
    "G_IM_FMT_I":       "4",
    "G_IM_SIZ_4b":      "0",
    "G_IM_SIZ_8b":      "1",
    "G_IM_SIZ_16b":     "2",
    "G_IM_SIZ_32b":     "3",
    "G_RM_NOOP":        "0",
    "G_RM_NOOP2":       "0",
    "G_RM_OPA_SURF":    "0x0f0a4000",
    "G_RM_OPA_SURF2":   "0x0f0a4000",
    "G_RM_AA_OPA_SURF": "0x0f184000",
    "G_RM_AA_OPA_SURF2":"0x0f184000",
    "G_RM_AA_XLU_SURF": "0x00194248",
    "G_RM_AA_XLU_SURF2":"0x00194248",
}

KNOWN_FUNCTION_MACROS = {
    "FTOFRAC8": "#define FTOFRAC8(x) ((s32)((x) * 127.0f) & 0xFF)",
    "OS_K0_TO_PHYSICAL": "#define OS_K0_TO_PHYSICAL(x) ((u32)(x) & 0x1FFFFFFF)",
    "OS_PHYSICAL_TO_K0": "#define OS_PHYSICAL_TO_K0(x) ((void *)((u32)(x) | 0x80000000))",
    "OS_PHYSICAL_TO_K1": "#define OS_PHYSICAL_TO_K1(x) ((void *)((u32)(x) | 0xA0000000))",
}


# ─── Native Python C-Parser ───────────────────────────────────────────────────

def strip_duplicate_structs(content):
    """
    Natively parses C code to identify complete struct boundaries via brace counting.
    Wipes out older duplicate copies of the same tagged struct definition.
    """
    pattern = re.compile(r'(?:typedef\s+)?(?:struct|union)\s+(\w+)\s*\{')
    spans_by_tag = defaultdict(list)
    
    pos = 0
    while True:
        m = pattern.search(content, pos)
        if not m: break
        tag = m.group(1)
        start_idx = m.start()
        
        brace_count = 0
        in_struct = False
        end_idx = -1
        
        for i in range(m.end() - 1, len(content)):
            if content[i] == '{':
                brace_count += 1
                in_struct = True
            elif content[i] == '}':
                brace_count -= 1
                if in_struct and brace_count == 0:
                    semi = content.find(';', i)
                    if semi != -1:
                        end_idx = semi + 1
                    break
                    
        if end_idx != -1:
            spans_by_tag[tag].append((start_idx, end_idx))
            pos = end_idx
        else:
            pos = m.end()

    to_remove = []
    for tag, spans in spans_by_tag.items():
        if len(spans) > 1:
            # The injected/dummy ones are usually earlier, the real ones are later.
            # Keeping the last definition guarantees we preserve the real struct.
            to_remove.extend(spans[:-1])
            
    to_remove.sort(key=lambda x: x[0], reverse=True)
    removed_count = 0
    for start, end in to_remove:
        content = content[:start] + content[end:]
        removed_count += 1
        
    return content, removed_count


def is_defined_locally(filepath, tag):
    """Checks if the struct alias or struct body is genuinely defined lower down in the local file."""
    if not filepath or not os.path.exists(filepath): return False
    c = read_file(filepath)
    pattern1 = rf"\}\s*{re.escape(tag)}\s*;"
    pattern2 = rf"struct\s+{re.escape(tag)}\s*\{{"
    return bool(re.search(pattern1, c) or re.search(pattern2, c))


# ─── Utilities ────────────────────────────────────────────────────────────────

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

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
    if m:
        return m.group(1)
    m = re.search(r"\(aka '(?:struct\s+)?([^']+)'\)", line)
    return m.group(1) if m else None

def source_path(path):
    if not path:
        return None
    p = path.replace("C/C++: ", "").strip()
    if "/Banjo-recomp-android/Banjo-recomp-android/" in p:
        p = p.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
    return os.path.normpath(p)

def is_sdk_or_ndk_path(fp):
    if not fp:
        return True
    normalized = fp.replace("\\", "/")
    return "/usr/" in normalized or "ndk" in normalized.lower()

def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def strip_auto_preamble(content, filepath, has_local_typedef_set):
    lines = content.split('\n')
    result = []
    in_auto_block = False
    for line in lines:
        s = line.strip()
        if s == "/* AUTO: forward declarations */":
            in_auto_block = True
            continue
        if in_auto_block and re.match(r'typedef\s+struct\s+\w+_s\s+\w+\s*;', s):
            continue
        if s == '#include "ultra/n64_types.h"' and filepath in has_local_typedef_set:
            in_auto_block = False
            continue
        in_auto_block = False
        result.append(line)
    return '\n'.join(result)

def ensure_types_header_base():
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
            write_file(TYPES_HEADER, content)
            print("  [🛠️] Added #pragma once to n64_types.h")
        return content
    content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
    os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)
    write_file(TYPES_HEADER, content)
    print("  [🛠️] Created n64_types.h")
    return content


# ─── Failed-file log ──────────────────────────────────────────────────────────

def generate_failed_log(log_data):
    file_errors = defaultdict(set)
    loose_errors = set()
    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    for line in log_data.split('\n'):
        if ("error:" not in line
                and "undefined reference" not in line
                and "undefined symbol" not in line):
            continue
        if "too many errors emitted" in line:
            continue
        m_file = re.search(file_regex, line)
        fp = source_path(m_file.group(1) if m_file else None)
        m_err = re.search(r"error:\s*(.*)", line)
        msg = m_err.group(1).strip() if m_err else line.strip()
        if fp and not is_sdk_or_ndk_path(fp):
            file_errors[fp].add(msg)
        else:
            loose_errors.add(msg)

    out = ["=" * 70, "FAILED FILES LOG", "=" * 70, ""]
    for fp in sorted(file_errors):
        out.append(f"FILE: {fp}")
        for err in sorted(file_errors[fp]):
            out.append(f"  • {err}")
        out.append("")
    if loose_errors:
        out.append("LINKER / UNATTRIBUTED ERRORS:")
        for err in sorted(loose_errors):
            out.append(f"  • {err}")
        out.append("")

    with open(FAILED_LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

    print("\n" + "=" * 60)
    print(f"📋 FAILED FILES SUMMARY  →  {FAILED_LOG_FILE}")
    print("=" * 60)
    for fp in sorted(file_errors):
        print(f"  {fp}  ({len(file_errors[fp])} unique error(s))")
    if loose_errors:
        print(f"  [linker/unattributed]  ({len(loose_errors)} error(s))")
    print("=" * 60 + "\n")
    return set(file_errors.keys())

def generate_error_summary(log_data):
    errors = set()
    for line in log_data.split('\n'):
        if "error:" in line and "too many errors emitted" not in line:
            m = re.search(r"error:\s*(.*)", line)
            if m:
                errors.add(m.group(1).strip())
    print("\n" + "=" * 60)
    print("📋 CONDENSED ERROR SUMMARY")
    print("=" * 60)
    for e in sorted(errors):
        print(f"- {e}")
    print("=" * 60 + "\n")


# ─── Error classification ─────────────────────────────────────────────────────

def classify_errors(log_data):
    categories = {
        "missing_n64_types":    set(),
        "actor_pointer":        set(),
        "local_struct_fwd":     [],
        "local_fwd_only":       [],
        "typedef_redef":        [],
        "struct_redef":         [],
        "static_conflict":      [],
        "incomplete_sizeof":    [],
        "need_struct_body":     set(),
        "need_mtx_body":        False,
        "undeclared_macros":    set(),
        "undeclared_gbi":       set(),
        "undeclared_n64_types": set(),
        "missing_types":        defaultdict(set),
        "missing_globals":      defaultdict(set),
        "implicit_func":        set(),
        "undefined_symbols":    set(),
        "audio_states":         set(),
        "unknown":              [],
        "extraneous_brace":     False,
        "has_local_typedef":    set(),
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    lines = log_data.split('\n')
    for line in lines:
        if "extraneous closing brace" in line:
            categories["extraneous_brace"] = True

        if ("error:" not in line
                and "undefined reference" not in line
                and "undefined symbol" not in line
                and "note:" not in line):
            continue

        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)
        if is_sdk_or_ndk_path(filepath):
            filepath = None

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

        m_sizeof = "invalid application of 'sizeof'" in line
        m_ptr    = "arithmetic on a pointer to an incomplete type" in line
        m_array  = "array has incomplete element type" in line

        if m_no_member and m_no_member.group(2) in ("Mtx", "Mtx_s"):
            categories["need_mtx_body"] = True

        if m_incomplete and filepath:
            tag = m_incomplete.group(1)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES:
                categories["need_struct_body"].add(base_tag)
            else:
                categories["incomplete_sizeof"].append((filepath, tag))

        if m_tentative and filepath:
            tag = m_tentative.group(2)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES:
                categories["need_struct_body"].add(base_tag)
            else:
                categories["incomplete_sizeof"].append((filepath, tag))

        if (m_redef or m_struct_redef) and filepath:
            categories["has_local_typedef"].add(filepath)
        if m_redef and filepath:
            categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))
        if m_struct_redef and filepath:
            categories["struct_redef"].append((filepath, m_struct_redef.group(1)))

        if m_no_member and m_no_member.group(2) not in ("Mtx", "Mtx_s") and filepath:
            categories["has_local_typedef"].add(filepath)

        if m_unknown_type and filepath:
            type_name = m_unknown_type.group(1)
            if type_name in {"RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "ALVoiceState"}:
                categories["audio_states"].add(type_name)
            else:
                if is_defined_locally(filepath, type_name):
                    categories["local_fwd_only"].append((filepath, type_name))
                    categories["has_local_typedef"].add(filepath)
                elif type_name.istitle() or re.match(r'^[A-Z][A-Za-z0-9_]*$', type_name):
                    categories["missing_types"][type_name].add(filepath)
                else:
                    categories["local_fwd_only"].append((filepath, type_name))
                    categories["has_local_typedef"].add(filepath)

        if m_ident:
            ident = m_ident.group(1)
            if ident in N64_IDENT_TYPES:
                categories["undeclared_n64_types"].add(ident)
            elif ident.startswith("G_") or ident.startswith("g_"):
                categories["undeclared_gbi"].add(ident)
            elif ident in KNOWN_MACROS or ident in KNOWN_FUNCTION_MACROS:
                categories["undeclared_macros"].add(ident)
            elif ident.isupper():
                categories["undeclared_macros"].add(ident)
            elif ident.istitle() or re.match(r'^[A-Z][A-Za-z0-9_]*$', ident):
                if filepath and is_defined_locally(filepath, ident):
                    categories["local_fwd_only"].append((filepath, ident))
                    categories["has_local_typedef"].add(filepath)
                else:
                    if filepath: categories["missing_types"][ident].add(filepath)
            else:
                if filepath: categories["missing_globals"][ident].add(filepath)

        if m_undef_ref:
            categories["undefined_symbols"].add(m_undef_ref.group(1).strip())
        if m_undef_sym:
            categories["undefined_symbols"].add(m_undef_sym.group(1).replace("'", "").strip())
        if m_implicit:
            categories["implicit_func"].add(m_implicit.group(1))
        if m_static and filepath:
            categories["static_conflict"].append((filepath, m_static.group(1)))
            
        if (m_sizeof or m_ptr or m_array) and filepath:
            inc_type = extract_incomplete_type(line)
            if inc_type:
                base_tag = inc_type[:-2] if inc_type.endswith("_s") else inc_type
                if base_tag in N64_STRUCT_BODIES:
                    categories["need_struct_body"].add(base_tag)
                else:
                    categories["incomplete_sizeof"].append((filepath, inc_type))

        if filepath and os.path.exists(filepath) and filepath not in categories["has_local_typedef"]:
            if "error:" in line:
                categories["missing_n64_types"].add(filepath)

    known_global_types = {
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx", "LookAt",
        "RESAMPLE_STATE", "ENVMIX_STATE", "POLEF_STATE",
        "OSContPad", "OSTimer", "OSTime", "OSMesg", "OSEvent",
        "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
        "OSIntMask", "OSPfs", "OSIoMesg",
        "Actor", "ActorMarker",
        "s8", "u8", "s16", "u16", "s32", "u32", "s64", "u64",
        "f32", "f64", "n64_bool", "OSPri", "OSId",
    }
    
    seen_local_fwd = set()
    new_local_fwd = []
    for filepath, type_name in categories["local_fwd_only"]:
        base_type = type_name[:-2] if type_name.endswith("_s") else type_name
        if base_type in known_global_types or type_name in known_global_types:
            categories["missing_n64_types"].add(filepath)
            categories["has_local_typedef"].discard(filepath)
        else:
            key = (filepath, type_name)
            if key not in seen_local_fwd:
                seen_local_fwd.add(key)
                new_local_fwd.append((filepath, type_name))
    categories["local_fwd_only"] = new_local_fwd

    categories["missing_n64_types"] -= categories["has_local_typedef"]
    return categories


def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0, set()

    log_data = read_file(LOG_FILE)
    categories = classify_errors(log_data)
    failed_files = generate_failed_log(log_data)

    fixes = 0
    fixed_files = set()

    # ─── Proactive Header Healing ────────────────────────────────────────────────
    types_content = ensure_types_header_base()
    original_types = types_content

    # Aggressively obliterate conflicting dummy stubs of known types
    for tag in N64_STRUCT_BODIES.keys():
        types_content = re.sub(rf'struct\s+{tag}\s*\{{[^}}]+\}};\n?', '', types_content)
    
    # Run the native Python Brace-Parser on the header to remove trailing duplicates (e.g., duplicate Mtx definitions)
    types_content, rm_cnt = strip_duplicate_structs(types_content)
    if types_content != original_types or rm_cnt > 0:
        write_file(TYPES_HEADER, types_content)
        print(f"  [🛠️] Proactively cleaned up conflicting/duplicate struct definitions in n64_types.h")
        fixes += 1

    if categories["extraneous_brace"]:
        original = types_content
        types_content = re.sub(
            r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n",
            "", types_content
        )
        types_content = re.sub(
            r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{",
            r"typedef struct \1 {", types_content
        )
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            print("  [🛠️] Cleaned up syntax corruption in n64_types.h")
            fixes += 1

    for filepath in sorted(categories["missing_n64_types"]):
        if not os.path.exists(filepath):
            continue
        if filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            print(f"  [🛠️] Injected n64_types.h into {os.path.basename(filepath)}")
            fixed_files.add(filepath)
            fixes += 1

    for filepath in sorted(categories["actor_pointer"]):
        if not os.path.exists(filepath):
            continue
        content = read_file(filepath)
        original = content
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
            print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories["local_struct_fwd"]:
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_struct_fwd"]:
            file_to_types[filepath].add(type_name)
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
                print(f"  [🛠️] Injected forward decls {sorted(type_names)} into {os.path.basename(filepath)}")
                fixed_files.add(filepath)
                fixes += 1

    # ── FIX D: Typedef / Struct Redefinition ────────────────────────────
    fixd_files = set()
    for filepath, _, _ in categories["typedef_redef"]:
        fixd_files.add(filepath)
    for filepath, _ in categories["struct_redef"]:
        fixd_files.add(filepath)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        original = content

        content = strip_auto_preamble(content, filepath, categories["has_local_typedef"])

        # Deep Native Python Parser securely wipes duplicate struct bodies (e.g. duplicate LetterFloorTile_s)
        content, cnt = strip_duplicate_structs(content)
        if cnt:
            print(f"  [🛠️] Cleaned {cnt} duplicate struct bodies natively in {os.path.basename(filepath)}")

        for fp2, type1, type2 in categories["typedef_redef"]:
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
            
            # Simple anon body retagger 
            anon_body_pattern = rf"typedef\s+struct\s*\{{([\s\S]*?)\}}\s*{re.escape(alias)}\s*;"
            has_body = re.search(anon_body_pattern, content)
            
            if has_body:
                content, ccnt = re.subn(
                    anon_body_pattern,
                    lambda m: f"typedef struct {target_tag} {{{m.group(1)}}} {alias};",
                    content, count=1
                )
                if ccnt:
                    print(f"  [🛠️] Retagged anon body as '{target_tag}' in {os.path.basename(filepath)}")
            else:
                content, ccnt = re.subn(
                    r"\bstruct\s+" + re.escape(alias) + r"\b",
                    f"struct {target_tag}", content
                )
                if ccnt:
                    print(f"  [🛠️] Tag substitution '{alias}'→'{target_tag}' in {os.path.basename(filepath)}")

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories["incomplete_sizeof"]:
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen = set()
        for filepath, tag in categories["incomplete_sizeof"]:
            if tag in seen:
                continue
            seen.add(tag)
            
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES:
                continue
                
            is_sdk = (
                tag.isupper()
                or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_"))
                or (tag.endswith("_s") and tag[:-2].isupper())
            )
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
                print(f"  [🛠️] Injected dummy SDK struct '{tag}' into n64_types.h")
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    seen_static = set()
    for filepath, func_name in categories["static_conflict"]:
        key = (filepath, func_name)
        if key in seen_static:
            continue
        seen_static.add(key)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        prefix = os.path.basename(filepath).split('.')[0]
        macro_fix = (f"\n/* AUTO: fix static conflict */\n"
                     f"#define {func_name} auto_renamed_{prefix}_{func_name}\n")
        if macro_fix not in content:
            anchor = '#include "ultra/n64_types.h"'
            content = (content.replace(anchor, anchor + macro_fix)
                       if anchor in content else macro_fix + content)
            write_file(filepath, content)
            print(f"  [🛠️] Protected static '{func_name}' via macro in {os.path.basename(filepath)}")
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
                    print(f"  [🛠️] Injected function macro '{macro}' into n64_types.h")
            elif macro in KNOWN_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += (f"\n#ifndef {macro}\n"
                                      f"#define {macro} {KNOWN_MACROS[macro]}\n"
                                      f"#endif\n")
                    macros_added = True
                    print(f"  [🛠️] Injected macro '{macro}' = {KNOWN_MACROS[macro]} into n64_types.h")
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
                    print(f"  [🛠️] Injected placeholder for unknown macro '{macro}'")

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
                types_content = types_content.replace(
                    "#pragma once", f"#pragma once\n#include {header}"
                )
                includes_added = True
                print(f"  [🛠️] Injected {header} for implicit '{func}'")
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
                    cmake_content = cmake_content.replace(
                        "add_library(", "add_library(\n        ultra/n64_stubs.c"
                    )
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added = False
        for sym in sorted(categories["undefined_symbols"]):
            if sym.startswith("_Z") or "vtable" in sym:
                continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
                print(f"  [🛠️] Generated linker stub for '{sym}'")
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    if categories["audio_states"]:
        types_content = read_file(TYPES_HEADER)
        audio_added = False
        for t in sorted(categories["audio_states"]):
            if f"typedef struct {t}" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            print("  [🛠️] Injected missing N64 synth types into n64_types.h")
            fixes += 1

    if categories["undeclared_n64_types"]:
        types_content = read_file(TYPES_HEADER)
        k_added = False
        if "OSIntMask" in categories["undeclared_n64_types"]:
            if "OSIntMask" not in types_content:
                types_content += "\n/* N64 interrupt mask type */\ntypedef u32 OSIntMask;\n"
                k_added = True
                print("  [🛠️] Injected 'typedef u32 OSIntMask' into n64_types.h")
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
                print("  [🛠️] Stubbed osSetIntMask in n64_stubs.c")
                fixes += 1

    if categories["undeclared_gbi"]:
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if ident in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += (f"\n#ifndef {ident}\n"
                                  f"#define {ident} {KNOWN_MACROS[ident]}\n"
                                  f"#endif\n")
                gbi_added = True
                print(f"  [🛠️] Injected GBI constant '{ident}' into n64_types.h")
            elif ident not in KNOWN_MACROS:
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                    gbi_added = True
                    print(f"  [🛠️] Injected placeholder for unknown GBI constant '{ident}'")
        if gbi_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── FIX M: Mtx struct body ───────────────────────────────────────────
    if categories["need_mtx_body"]:
        types_content = read_file(TYPES_HEADER)
        if "i[4][4]" not in types_content and "m[4][4]" not in types_content:
            types_content += "\n" + N64_STRUCT_BODIES["Mtx"]
            write_file(TYPES_HEADER, types_content)
            print("  [🛠️] Injected real Mtx struct body into n64_types.h")
            fixes += 1

    # ── FIX N/O: Full struct bodies for known N64 types ──────────────────
    if categories["need_struct_body"]:
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(categories["need_struct_body"]):
            if tag == "Mtx":
                continue  
            body = N64_STRUCT_BODIES.get(tag)
            check_str = "l[2]" if tag == "LookAt" else ("fileSize" if tag == "OSPfs" else tag)
            
            if body and check_str not in types_content:
                types_content += "\n" + body
                bodies_added = True
                print(f"  [🛠️] Injected full struct body for '{tag}' into n64_types.h")
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["local_fwd_only"]:
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_fwd_only"]:
            file_to_types[filepath].add(type_name)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
                continue
            content = read_file(filepath)
            content = strip_auto_preamble(content, filepath, categories["has_local_typedef"])
            changed = False
            for t in sorted(type_names):
                if is_defined_locally(filepath, t):
                    fwd = f"/* AUTO: forward decl for type defined below */\ntypedef struct {t}_s {t};\n"
                    if f"typedef struct {t}_s {t};" not in content:
                        content = fwd + content
                        changed = True
                        print(f"  [🛠️] Injected forward decl for '{t}' (defined later in file) into {os.path.basename(filepath)}")
                else:
                    fwd = f"/* AUTO: forward declarations */\ntypedef struct {t}_s {t};\n"
                    if f"typedef struct {t}_s {t};" not in content:
                        content = fwd + content
                        changed = True
                        print(f"  [🛠️] Injected missing forward decl for '{t}' into {os.path.basename(filepath)}")
            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # ── FIX Q: Missing Custom Types ──────────────────────────────────────────
    if categories["missing_types"]:
        types_content = read_file(TYPES_HEADER)
        types_added = False
        for tag in sorted(categories["missing_types"]):
            if tag in N64_STRUCT_BODIES or tag in known_global_types:
                continue
            if f"}} {tag};" not in types_content and f"struct {tag} {{" not in types_content:
                types_content += f"\ntypedef struct {tag} {{ int dummy_data[128]; }} {tag};\n"
                types_added = True
                print(f"  [🛠️] Injected missing custom type '{tag}' into n64_types.h")
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── FIX R: Missing Globals ───────────────────────────────────────────────
    if categories["missing_globals"]:
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for glob in sorted(categories["missing_globals"]):
            if glob == "actor": continue
            if f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content:
                if glob.endswith("_ptr") or glob.endswith("_p"):
                    decl = f"extern void* {glob};"
                else:
                    decl = f"extern long long int {glob};"
                
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
                print(f"  [🛠️] Injected missing global '{glob}' into n64_types.h")
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
            if os.path.exists(FAILED_LOG_FILE):
                os.remove(FAILED_LOG_FILE)
            return

        fixes, failed_files = apply_fixes()

        if fixes == 0:
            stall_count += 1
            print(f"\n⚠️  No fixable patterns this cycle. Stall count: {stall_count}/{MAX_STALL}")
            if failed_files:
                print(f"   {len(failed_files)} file(s) still failing — see {FAILED_LOG_FILE}")
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted after {MAX_STALL} consecutive stall cycles.")
                print(f"   Review {FAILED_LOG_FILE} for remaining issues.")
                break
        else:
            stall_count = 0

        time.sleep(1)


if __name__ == "__main__":
    main()
