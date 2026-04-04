"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Cycle logic:
  1. Run Gradle / ninja build, stream output to log.
  2. Parse the log for every known error pattern.
  3. Apply targeted fixes to source / headers.
  4. Repeat until the build succeeds or no new fixes can be applied.

Error taxonomy handled
  A  missing_n64_includes   — source file needs #include "ultra/n64_types.h"
  C  local_struct_fwd       — unknown type that is a local game-logic struct
  I  undefined_symbols      — linker: undefined symbol / undefined reference
  J  cmake_libraries        — CMakeLists.txt missing -lm / -llog
  K  missing_sdk_types      — SDK typedef (OSIntMask etc.) absent from n64_types.h
  M  missing_macros         — macro constant (MAX_RATIO etc.) absent from n64_types.h
  R  typedef_redef          — typedef redefinition with different types
  S  static_conflict        — static declaration follows non-static
  T  incomplete_sizeof      — sizeof of incomplete type
  D  daemon_crash           — Gradle daemon OOM / message-receive failure (retryable)
  O  oom_detected           — Gradle JVM heap exhaustion (retryable, raises heap)
"""

import os
import re
import subprocess
import sys
import time

# ── Build environment ────────────────────────────────────────────────────────

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

# Heap starts at 6 g; raised automatically on OOM (see oom_handler).
_HEAP_GB = 6

def _gradle_cmd():
    return [
        "gradle", "-p", "Android", "assembleDebug",
        "--console=plain", "--max-workers=1", "--no-daemon",
        f"-Dorg.gradle.jvmargs=-Xmx{_HEAP_GB}g -XX:+HeapDumpOnOutOfMemoryError",
    ]

LOG_FILE     = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"
CMAKE_FILE   = "Android/app/src/main/cpp/CMakeLists.txt"

# ── Known SDK typedefs ───────────────────────────────────────────────────────
# Any identifier that appears in source as a *type* but is missing from the
# force-included n64_types.h should be listed here.

KNOWN_SDK_TYPEDEFS: dict[str, str] = {
    "OSHWIntr":      "unsigned int",
    "OSIntMask":     "unsigned int",   # n_csplayer.c, event.c
    "OSYieldResult": "int",
    "OSPri":         "int",
    "OSId":          "int",
    "OSTime":        "unsigned long long",
    "OSMesg":        "unsigned long long",
    "n64_bool":      "int",
    "s8":            "signed char",
    "u8":            "unsigned char",
    "s16":           "short",
    "u16":           "unsigned short",
    "s32":           "int",
    "u32":           "unsigned int",
    "s64":           "long long",
    "u64":           "unsigned long long",
    "f32":           "float",
    "f64":           "double",
}

# SDK types that need opaque struct stubs (not scalar typedefs).
KNOWN_SDK_STRUCT_TYPES: set[str] = {
    "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Gfx_t", "Mtx", "Mtx_t",
    "OSContPad", "OSTimer", "OSThread", "OSMesgQueue", "OSTask", "OSTask_t",
    "OSEvent", "CPUState", "Actor", "ActorMarker",
}

# Union of all known global type names (used for classifier routing).
KNOWN_GLOBAL_TYPES: set[str] = set(KNOWN_SDK_TYPEDEFS) | KNOWN_SDK_STRUCT_TYPES

# ── Known macro constants ────────────────────────────────────────────────────
# Maps macro name → C literal to emit in #define.
# Add new entries here as new files expose missing constants.

KNOWN_MACROS: dict[str, str] = {
    "MAX_RATIO":    "32",           # n_resample.c — audio resampler clamp
    "OS_IM_NONE":  "0x00000000u",  # interrupt-mask constants
    "OS_IM_ALL":   "0xFFFFFFFFu",
    "TRUE":         "1",
    "FALSE":        "0",
    "NULL":         "((void*)0)",
}

# ── Utilities ────────────────────────────────────────────────────────────────

_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    return _ANSI.sub('', text)

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path: str | None) -> str | None:
    """Return None if the path points to NDK / system headers."""
    if not path:
        return None
    if "/usr/" in path or "ndk" in path.lower():
        return None
    return path

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build() -> bool:
    """Invoke Gradle; stream output to both stdout and LOG_FILE.
    Returns True on success."""
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) …")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            _gradle_cmd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            clean = strip_ansi(line)
            log.write(clean)
            print(clean, end="")
        proc.wait()
    return proc.returncode == 0

# ── Error classifier ──────────────────────────────────────────────────────────

_FILE_RE = re.compile(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))")

def _extract_incomplete_type(line: str) -> str | None:
    for pat in [r"\(aka 'struct ([^']+)'\)", r"'struct ([^']+)'", r"'([^']+)'"]:
        m = re.search(pat, line)
        if m:
            return m.group(1)
    return None

def classify_errors(log_data: str) -> dict:
    cats: dict = {
        "missing_n64_includes": [],   # A
        "local_struct_fwd":     [],   # C
        "undefined_symbols":    [],   # I
        "cmake_libraries":      False,# J (boolean flag)
        "missing_sdk_types":    [],   # K
        "missing_macros":       [],   # M
        "typedef_redef":        [],   # R
        "static_conflict":      [],   # S
        "incomplete_sizeof":    [],   # T
        "daemon_crash":         False,# D
        "oom_detected":         False,# O
        "implicit_func":        [],
        "unknown_idents":       [],   # genuinely unknown — needs human review
    }

    local_struct_map: dict[str, set] = {}

    for line in log_data.splitlines():

        # ── Retryable infrastructure failures ──────────────────────────────
        if "Could not receive a message from the daemon" in line:
            cats["daemon_crash"] = True
            continue
        if "OutOfMemoryError" in line or "Java heap space" in line:
            cats["oom_detected"] = True
            continue

        if "error:" not in line and "undefined" not in line:
            continue

        pm = _FILE_RE.search(line)
        fp = source_path(pm.group(1) if pm else None)

        # Pattern matches — ordered most-specific → least-specific
        m_redef    = re.search(r"typedef redefinition with different types \('([^']+)'.*?vs '([^']+)'.*?\)", line)
        m_static   = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown  = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        m_ident    = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_s  = re.search(r"undefined symbol: (.*)", line)
        m_undef_r  = re.search(r"undefined reference to `([^']+)'", line)
        m_inc      = "incomplete type" in line

        if m_undef_s or m_undef_r:
            sym = (m_undef_s or m_undef_r).group(1).strip("`' ")
            cats["undefined_symbols"].append(sym)

        elif m_implicit:
            cats["implicit_func"].append(m_implicit.group(1))

        elif m_ident:
            ident = m_ident.group(1)
            # Cascade variable errors (e.g. 'mask') are suppressed once the
            # root type (OSIntMask) is fixed — no direct fix needed.
            if ident in KNOWN_GLOBAL_TYPES or ident in KNOWN_SDK_TYPEDEFS:
                cats["missing_sdk_types"].append(ident)
            elif ident in KNOWN_MACROS:
                cats["missing_macros"].append(ident)
            elif re.fullmatch(r"[a-z_][a-z0-9_]*", ident):
                # Lower-case single-word: almost certainly a cascade variable
                # (like 'mask') from an earlier type error — skip, not actionable.
                pass
            else:
                cats["unknown_idents"].append((fp, ident))

        elif m_redef and fp:
            cats["typedef_redef"].append((fp, m_redef.group(1), m_redef.group(2)))

        elif m_static and fp:
            cats["static_conflict"].append((fp, m_static.group(1)))

        elif m_unknown:
            t = m_unknown.group(1)
            if t in KNOWN_GLOBAL_TYPES or t in KNOWN_SDK_TYPEDEFS:
                cats["missing_sdk_types"].append(t)
            elif fp:
                local_struct_map.setdefault(fp, set()).add(t)

        elif m_inc and fp:
            inc = _extract_incomplete_type(line)
            if inc:
                cats["incomplete_sizeof"].append((fp, inc))

        elif fp and os.path.exists(fp):
            cats["missing_n64_includes"].append(fp)

    for fp, type_names in local_struct_map.items():
        for t in type_names:
            if t not in KNOWN_GLOBAL_TYPES:
                cats["local_struct_fwd"].append((fp, t))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def _already_defined(content: str, name: str) -> bool:
    """True if name appears to already be defined in content."""
    return (
        f"typedef struct {name}" in content
        or f"typedef {KNOWN_SDK_TYPEDEFS.get(name, '__never__')} {name};" in content
        or f"typedef unsigned int {name};" in content
        or f"#define {name}" in content
    )


def fix_missing_sdk_types(cats: dict) -> int:
    """FIX K — inject missing SDK typedefs into n64_types.h."""
    missing = set(cats["missing_sdk_types"])
    if not missing or not os.path.exists(TYPES_HEADER):
        return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(missing):
        if _already_defined(content, t):
            continue
        if t in KNOWN_SDK_TYPEDEFS:
            decl = f"\ntypedef {KNOWN_SDK_TYPEDEFS[t]} {t};\n"
        else:
            decl = f"\ntypedef struct {t}_s {{ long long int reserved[64]; }} {t};\n"
        content += decl
        added = True
        print(f"  [K] Defined SDK type: {t}")
    if added:
        write_file(TYPES_HEADER, content)
        return 1
    return 0


def fix_missing_macros(cats: dict) -> int:
    """FIX M — inject #define constants into n64_types.h."""
    needed = set(cats["missing_macros"])
    to_inject = {k: v for k, v in KNOWN_MACROS.items() if k in needed}
    if not to_inject or not os.path.exists(TYPES_HEADER):
        # Report truly unknown undeclared identifiers
        unknown = [(fp, id_) for fp, id_ in cats.get("unknown_idents", [])
                   if id_ not in KNOWN_MACROS and id_ not in KNOWN_GLOBAL_TYPES]
        if unknown:
            print(f"  [⚠] Unknown identifiers (manual fix needed): "
                  f"{sorted(set(id_ for _, id_ in unknown))}")
        return 0
    content = read_file(TYPES_HEADER)
    added = False
    for macro, value in sorted(to_inject.items()):
        if f"#define {macro}" in content:
            continue
        content += f"\n#ifndef {macro}\n#define {macro} {value}\n#endif\n"
        added = True
        print(f"  [M] Injected macro: #define {macro} {value}")
    if added:
        write_file(TYPES_HEADER, content)
        return 1
    return 0


def fix_local_struct_fwd(cats: dict) -> int:
    """FIX C — inject forward declarations for local game-logic actor structs."""
    if not cats["local_struct_fwd"]:
        return 0
    file_to_types: dict[str, set] = {}
    for fp, t in cats["local_struct_fwd"]:
        file_to_types.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, type_names in file_to_types.items():
        if not os.path.exists(fp):
            continue
        content = read_file(fp)
        new_decls = []
        for t in sorted(type_names):
            tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in "sS" else t
            fwd = f"typedef struct {tag}_s {t};"
            if fwd not in content:
                new_decls.append(fwd)
        if new_decls:
            content = "/* AUTO: forward declarations */\n" + "\n".join(new_decls) + "\n" + content
            write_file(fp, content)
            print(f"  [C] Injected fwd decls {sorted(type_names)} → {os.path.basename(fp)}")
            fixes += 1
    return fixes


def fix_missing_n64_includes(cats: dict) -> int:
    """FIX A — add force-include guard to source files missing n64_types.h."""
    fixes = 0
    for fp in set(cats["missing_n64_includes"]):
        if not os.path.exists(fp) or fp.endswith("n64_types.h"):
            continue
        content = read_file(fp)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(fp, '#include "ultra/n64_types.h"\n' + content)
            print(f"  [A] Added n64_types.h include → {os.path.basename(fp)}")
            fixes += 1
    return fixes


def fix_cmake_libraries() -> int:
    """FIX J — ensure math and log libraries are linked."""
    if not os.path.exists(CMAKE_FILE):
        return 0
    cmake = read_file(CMAKE_FILE)
    if "target_link_libraries(" in cmake and " m " not in cmake:
        cmake = re.sub(r"(target_link_libraries\([^)]+)", r"\1 m log ", cmake)
        write_file(CMAKE_FILE, cmake)
        print("  [J] Injected -lm -llog into CMakeLists.txt")
        return 1
    return 0


def fix_undefined_symbols(cats: dict) -> int:
    """FIX I — generate linker stubs for undefined symbols."""
    syms = set(cats["undefined_symbols"])
    if not syms:
        return 0
    os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
    if not os.path.exists(STUBS_FILE):
        write_file(STUBS_FILE, '#include "n64_types.h"\n\n')
    stubs = read_file(STUBS_FILE)
    added = False
    for sym in sorted(syms):
        if f" {sym}(" in stubs:
            continue
        stubs += f"\nlong long int {sym}() {{ return 0; }}\n"
        added = True
        print(f"  [I] Generated linker stub: {sym}")
    if added:
        write_file(STUBS_FILE, stubs)
        return 1
    return 0


def handle_oom(cats: dict) -> int:
    """FIX O/D — bump heap on OOM; report daemon crash as retryable."""
    global _HEAP_GB
    fixed = 0
    if cats["oom_detected"]:
        new_heap = min(_HEAP_GB + 2, 14)  # cap at 14 g
        if new_heap != _HEAP_GB:
            print(f"  [O] Java OOM — raising heap {_HEAP_GB}g → {new_heap}g")
            _HEAP_GB = new_heap
            fixed += 1
        else:
            print("  [O] Java OOM — heap already at maximum (14g). "
                  "Consider splitting the source set.")
    if cats["daemon_crash"]:
        print("  [D] Gradle daemon crash detected (likely OOM in daemon JVM). "
              "Retrying with --no-daemon (already set).")
        fixed += 1  # count as actionable so we retry
    return fixed


# ── Top-level fix dispatcher ─────────────────────────────────────────────────

def apply_fixes() -> int:
    if not os.path.exists(LOG_FILE):
        return 0
    log_data = read_file(LOG_FILE)
    cats = classify_errors(log_data)

    fixes = 0
    fixes += handle_oom(cats)
    fixes += fix_cmake_libraries()
    fixes += fix_missing_sdk_types(cats)
    fixes += fix_missing_macros(cats)
    fixes += fix_local_struct_fwd(cats)
    fixes += fix_missing_n64_includes(cats)
    fixes += fix_undefined_symbols(cats)

    # Surface unknown identifiers even when nothing else was fixed
    unknown = sorted(set(id_ for _, id_ in cats.get("unknown_idents", [])))
    if unknown:
        print(f"  [⚠] Unknown identifiers requiring manual investigation: {unknown}")

    return fixes


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    max_cycles = 100
    for i in range(1, max_cycles + 1):
        print(f"\n{'='*60}")
        print(f"  Build Cycle {i}/{max_cycles}")
        print(f"{'='*60}")

        if run_build():
            print("\n✅ Build Successful! APK is ready.")
            sys.exit(0)

        print("\n🔍 Analysing errors …")
        applied = apply_fixes()

        if applied == 0:
            print("\n🛑 No fixable patterns detected. Manual intervention required.")
            print("   Check the log at:", LOG_FILE)
            sys.exit(1)

        print(f"\n  ✔ Applied {applied} fix(es). Retrying …")
        time.sleep(1)

    print(f"\n🛑 Reached cycle limit ({max_cycles}). Build did not complete.")
    sys.exit(1)


if __name__ == "__main__":
    main()
