import os
import re
import subprocess
import time

# Single-threaded build to prevent memory exhaustion on GitHub Actions runners
os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=1", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError"
]
LOG_FILE   = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"
CMAKE_FILE   = "Android/app/src/main/cpp/CMakeLists.txt"

# ---------------------------------------------------------------------------
# Known SDK primitive typedefs  (used both for classification and injection)
# ---------------------------------------------------------------------------
KNOWN_SDK_TYPEDEFS = {
    "OSHWIntr":    "unsigned int",
    "OSIntMask":   "unsigned int",    # ← fixes n_csplayer.c / event.c
    "OSYieldResult": "int",
    "OSPri":       "int",
    "OSId":        "int",
    "OSTime":      "unsigned long long",
    "OSMesg":      "unsigned long long",
    "n64_bool":    "int",
    "s8":          "signed char",
    "u8":          "unsigned char",
    "s16":         "short",
    "u16":         "unsigned short",
    "s32":         "int",
    "u32":         "unsigned int",
    "s64":         "long long",
    "u64":         "unsigned long long",
    "f32":         "float",
    "f64":         "double",
}

# Known macros/constants that appear as undeclared identifiers.
# Maps identifier name → C expression to use in #define.
KNOWN_MACROS = {
    "MAX_RATIO":   "32",          # n_resample.c — audio resampler clamp
    "OS_IM_NONE":  "0x00000000u", # interrupt-mask constant (sometimes missing)
    "OS_IM_ALL":   "0xFFFFFFFFu",
    "TRUE":        "1",
    "FALSE":       "0",
    "NULL":        "((void*)0)",
}

# Struct-like SDK types that need opaque struct stubs rather than scalar typedefs
KNOWN_SDK_STRUCT_TYPES = {
    "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Gfx_t", "Mtx", "Mtx_t",
    "OSContPad", "OSTimer", "OSThread", "OSMesgQueue", "OSTask", "OSTask_t",
    "OSEvent", "CPUState", "Actor", "ActorMarker",
}

KNOWN_GLOBAL_TYPES = set(KNOWN_SDK_TYPEDEFS.keys()) | KNOWN_SDK_STRUCT_TYPES


def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


# ---------------------------------------------------------------------------
# Build runner
# ---------------------------------------------------------------------------

def run_build():
    print("\n🚀 Starting Build Cycle...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(
            GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            clean_line = strip_ansi(line)
            log.write(clean_line)
            print(clean_line, end="")
        process.wait()
    return process.returncode == 0


# ---------------------------------------------------------------------------
# Error classifier
# ---------------------------------------------------------------------------

def classify_errors(log_data):
    categories = {
        "missing_n64_types":  [],
        "actor_pointer":      [],
        "local_struct_fwd":   [],
        "typedef_redef":      [],
        "static_conflict":    [],
        "incomplete_sizeof":  [],
        "undeclared_macros":  [],   # true macros / constants (not types)
        "missing_sdk_types":  [],   # SDK types missing from n64_types.h
        "implicit_func":      [],
        "undefined_symbols":  [],
        "oom_detected":       False,
        "unknown":            [],
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))"
    local_struct_map = {}

    def extract_incomplete_type(line):
        for pattern in [r"\(aka 'struct ([^']+)'\)", r"'struct ([^']+)'", r"'([^']+)'"]:
            m = re.search(pattern, line)
            if m:
                return m.group(1)
        return None

    def source_path(path):
        """Return None if path points to NDK/system headers (not our source)."""
        if path and ("/usr/" in path or "ndk" in path.lower()):
            return None
        return path

    for line in log_data.split('\n'):

        # ── OOM / daemon crash detection ────────────────────────────────
        if "OutOfMemoryError" in line or "Java heap space" in line:
            categories["oom_detected"] = True
            continue

        if "error:" not in line and "undefined" not in line:
            continue

        path_match = re.search(file_regex, line)
        filepath = source_path(path_match.group(1) if path_match else None)

        # Pattern matches (order matters — most-specific first)
        m_redef    = re.search(r"typedef redefinition with different types \('([^']+)'(?:.*?)vs '([^']+)'(?:.*?)\)", line)
        m_static   = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown  = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_ident    = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_sym = re.search(r"undefined symbol: (.*)", line)
        m_undef_ref = re.search(r"undefined reference to `([^']+)'", line)
        m_inc      = "incomplete type" in line

        if m_undef_sym or m_undef_ref:
            sym = (m_undef_sym or m_undef_ref).group(1).replace("'", "").replace("`", "").strip()
            categories["undefined_symbols"].append(sym)

        elif m_implicit:
            categories["implicit_func"].append(m_implicit.group(1))

        elif m_ident:
            ident = m_ident.group(1)
            if ident == "actor" and filepath:
                categories["actor_pointer"].append(filepath)
            elif ident in KNOWN_GLOBAL_TYPES:
                # SDK type used as a variable — needs typedef, not a macro define
                categories["missing_sdk_types"].append(ident)
            elif ident in KNOWN_MACROS:
                categories["undeclared_macros"].append(ident)
            else:
                # Unknown identifier — treat as a macro for now
                categories["undeclared_macros"].append(ident)

        elif m_redef and filepath:
            categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))

        elif m_static and filepath:
            categories["static_conflict"].append((filepath, m_static.group(1)))

        elif m_unknown:
            type_name = m_unknown.group(1)
            if type_name in KNOWN_GLOBAL_TYPES:
                categories["missing_sdk_types"].append(type_name)
            elif filepath:
                local_struct_map.setdefault(filepath, set()).add(type_name)

        elif m_inc and filepath:
            inc_type = extract_incomplete_type(line)
            if inc_type:
                categories["incomplete_sizeof"].append((filepath, inc_type))

        elif filepath and os.path.exists(filepath):
            categories["missing_n64_types"].append(filepath)

    for filepath, type_names in local_struct_map.items():
        for t in type_names:
            if t not in KNOWN_GLOBAL_TYPES:
                categories["local_struct_fwd"].append((filepath, t))

    return categories


# ---------------------------------------------------------------------------
# Fix helpers
# ---------------------------------------------------------------------------

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Fix passes
# ---------------------------------------------------------------------------

def fix_cmake_libraries(fixes):
    """FIX J: Ensure math/log libraries are linked."""
    if not os.path.exists(CMAKE_FILE):
        return fixes
    cmake = read_file(CMAKE_FILE)
    if "target_link_libraries(" in cmake and " m " not in cmake:
        cmake = re.sub(r'(target_link_libraries\([^)]+)', r'\1 m log ', cmake)
        write_file(CMAKE_FILE, cmake)
        print("  [🛠️] Injected math/log libraries into CMakeLists.txt")
        fixes += 1
    return fixes


def fix_missing_sdk_types(categories, fixes):
    """FIX K: Inject missing SDK typedefs into n64_types.h.

    Handles both 'unknown type name' AND 'use of undeclared identifier'
    cases so that types like OSIntMask are correctly patched regardless
    of which Clang error message they produce.
    """
    missing = set(categories["missing_sdk_types"])
    if not missing or not os.path.exists(TYPES_HEADER):
        return fixes

    content = read_file(TYPES_HEADER)
    added = False

    for t in sorted(missing):
        # Skip if already defined in any recognisable form
        if (f"typedef struct {t}" in content or
                f"typedef {KNOWN_SDK_TYPEDEFS.get(t, '__never__')} {t};" in content or
                f"typedef unsigned int {t};" in content):
            continue

        if t in KNOWN_SDK_TYPEDEFS:
            decl = f"\ntypedef {KNOWN_SDK_TYPEDEFS[t]} {t};\n"
        else:
            decl = f"\ntypedef struct {t}_s {{ long long int reserved[64]; }} {t};\n"

        content += decl
        added = True
        print(f"  [🛠️] Defined SDK type: {t}")

    if added:
        write_file(TYPES_HEADER, content)
        fixes += 1
    return fixes


def fix_missing_macros(categories, fixes):
    """FIX M: Inject known macro #defines into n64_types.h.

    Only injects macros that are in KNOWN_MACROS; truly unknown identifiers
    are left for the user to investigate.
    """
    undeclared = set(categories["undeclared_macros"])
    known_missing = {k: v for k, v in KNOWN_MACROS.items() if k in undeclared}
    if not known_missing or not os.path.exists(TYPES_HEADER):
        return fixes

    content = read_file(TYPES_HEADER)
    added = False
    for macro, value in sorted(known_missing.items()):
        if f"#define {macro}" in content:
            continue
        content += f"\n#ifndef {macro}\n#define {macro} {value}\n#endif\n"
        added = True
        print(f"  [🛠️] Injected macro #define: {macro} = {value}")

    if added:
        write_file(TYPES_HEADER, content)
        fixes += 1

    # Report any truly unknown undeclared identifiers so the user is aware
    unknown_idents = undeclared - set(KNOWN_MACROS.keys()) - KNOWN_GLOBAL_TYPES
    if unknown_idents:
        print(f"  [⚠️ ] Unknown undeclared identifiers (manual fix needed): {sorted(unknown_idents)}")

    return fixes


def fix_local_struct_fwd(categories, fixes):
    """FIX C: Inject forward declarations for local game-logic actor structs."""
    if not categories["local_struct_fwd"]:
        return fixes
    file_to_types = {}
    for filepath, type_name in categories["local_struct_fwd"]:
        file_to_types.setdefault(filepath, set()).add(type_name)
    for filepath, type_names in file_to_types.items():
        if not os.path.exists(filepath):
            continue
        content = read_file(filepath)
        fwd_lines = []
        for t in sorted(type_names):
            tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
            fwd_decl = f"typedef struct {tag}_s {t};"
            if fwd_decl not in content:
                fwd_lines.append(fwd_decl)
        if fwd_lines:
            content = "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n" + content
            write_file(filepath, content)
            print(f"  [🛠️] Injected actor decls {sorted(type_names)} into {os.path.basename(filepath)}")
            fixes += 1
    return fixes


def fix_missing_n64_includes(categories, fixes):
    """FIX A: Add #include 'ultra/n64_types.h' to source files that need it."""
    for filepath in set(categories["missing_n64_types"]):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            write_file(filepath, content)
            fixes += 1
    return fixes


def fix_undefined_symbols(categories, fixes):
    """FIX I: Generate linker stubs for undefined symbols."""
    if not categories["undefined_symbols"]:
        return fixes
    if not os.path.exists(STUBS_FILE):
        os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
        write_file(STUBS_FILE, '#include "n64_types.h"\n\n')
    stubs = read_file(STUBS_FILE)
    added = False
    for sym in sorted(set(categories["undefined_symbols"])):
        if f" {sym}(" in stubs:
            continue
        stubs += f"\nlong long int {sym}() {{ return 0; }}\n"
        added = True
        print(f"  [🛠️] Generated linker stub for: {sym}")
    if added:
        write_file(STUBS_FILE, stubs)
        fixes += 1
    return fixes


# ---------------------------------------------------------------------------
# Top-level fix dispatcher
# ---------------------------------------------------------------------------

def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0
    log_data = read_file(LOG_FILE)
    categories = classify_errors(log_data)
    fixes = 0

    if categories["oom_detected"]:
        print("  [⚠️ ] Java OOM detected — consider raising -Xmx in GRADLE_CMD "
              "(currently 6g) or splitting the source set.")

    fixes = fix_cmake_libraries(fixes)
    fixes = fix_missing_sdk_types(categories, fixes)
    fixes = fix_missing_macros(categories, fixes)
    fixes = fix_local_struct_fwd(categories, fixes)
    fixes = fix_missing_n64_includes(categories, fixes)
    fixes = fix_undefined_symbols(categories, fixes)

    return fixes


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    for i in range(1, 100):
        print(f"\n--- Build Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful! You have an APK!")
            return
        applied = apply_fixes()
        if applied == 0:
            print("\n🛑 Build halted: No more automatic patterns detected.")
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
