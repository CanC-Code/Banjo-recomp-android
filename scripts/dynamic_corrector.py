"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Cycle logic:
  1. Run Gradle / ninja build, stream output to log.
  2. Parse the log for every known error pattern.
  3. Apply targeted fixes to source / headers.
  4. Repeat until the build succeeds or no new fixes can be applied.

Error taxonomy handled
  A  missing_n64_includes     — source file needs #include "ultra/n64_types.h"
  B  bad_fwd_injection        — our AUTO block used wrong struct tag; strip and re-inject correctly
  C  local_struct_fwd         — unknown type that is a local game-logic struct
  I  undefined_symbols        — linker: undefined symbol / undefined reference
  J  cmake_libraries          — CMakeLists.txt missing -lm / -llog
  K  missing_sdk_types        — SDK typedef (OSIntMask etc.) absent from n64_types.h
  M  missing_macros           — macro constant (MAX_RATIO etc.) absent from n64_types.h
  S  static_conflict          — static declaration follows non-static
  T  incomplete_sizeof        — sizeof of incomplete type
  D  daemon_crash             — Gradle daemon OOM / message-receive failure (retryable)
  O  oom_detected             — Gradle JVM heap exhaustion (retryable, raises heap)
"""

import os
import re
import subprocess
import sys
import time

# ── Build environment ────────────────────────────────────────────────────────

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

# Heap starts at 6 g; raised automatically on OOM (see handle_oom).
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

# Marker we prepend to all auto-injected forward-declaration blocks
AUTO_MARKER = "/* AUTO: forward declarations */"

# ── Known SDK typedefs ───────────────────────────────────────────────────────
KNOWN_SDK_TYPEDEFS = {
    "OSHWIntr":      "unsigned int",
    "OSIntMask":     "unsigned int",
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

KNOWN_SDK_STRUCT_TYPES = {
    "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Gfx_t", "Mtx", "Mtx_t",
    "OSContPad", "OSTimer", "OSThread", "OSMesgQueue", "OSTask", "OSTask_t",
    "OSEvent", "CPUState", "Actor", "ActorMarker",
}

KNOWN_GLOBAL_TYPES = set(KNOWN_SDK_TYPEDEFS) | KNOWN_SDK_STRUCT_TYPES

# ── Known macro constants ────────────────────────────────────────────────────
KNOWN_MACROS = {
    "MAX_RATIO":  "32",
    "OS_IM_NONE": "0x00000000u",
    "OS_IM_ALL":  "0xFFFFFFFFu",
    "TRUE":       "1",
    "FALSE":      "0",
    "NULL":       "((void*)0)",
}

# ── Utilities ────────────────────────────────────────────────────────────────

_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text):
    return _ANSI.sub('', text)

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path):
    """Return None if path is NDK/system, otherwise return path."""
    if not path:
        return None
    if "/usr/" in path or "ndk" in path.lower():
        return None
    return path

def strip_auto_block(content):
    """Remove our injected AUTO forward-declaration block from file content.
    The block starts with AUTO_MARKER and ends at the first blank line after
    all typedef lines, or at the first non-typedef, non-blank line."""
    if AUTO_MARKER not in content:
        return content, False
    # Robust strip: remove everything from the marker up to (but not including)
    # the first line that is NOT part of our block (i.e. not blank and not a
    # typedef line we would have generated).
    lines = content.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if AUTO_MARKER in line:
            start = i
            break
    if start is None:
        return content, False
    # Find where the block ends: first line after start that is not a typedef
    # or blank and does not contain another AUTO_MARKER line
    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped == "" or stripped.startswith("typedef struct") or AUTO_MARKER in stripped:
            end += 1
        else:
            break
    new_content = "".join(lines[:start]) + "".join(lines[end:])
    return new_content, True

def _real_struct_tag_for_typedef(content, typedef_name):
    """Scan the file's own source (after stripping our AUTO block) for
    `} typedef_name;` and extract the struct tag from the matching
    `typedef struct <tag> {` or `struct <tag> {` line above it.

    Returns the real tag string if found, else None.
    """
    # Pattern: closing brace of an inline struct def: "} TypedefName;"
    # We want the struct tag from the opening line.
    # Match both "typedef struct TAG {" and "struct TAG {"
    open_re  = re.compile(r"\bstruct\s+(\w+)\s*\{")
    close_re = re.compile(r"\}\s*" + re.escape(typedef_name) + r"\s*;")

    lines = content.splitlines()
    # Find the closing line
    close_idx = None
    for i, line in enumerate(lines):
        if close_re.search(line):
            close_idx = i
            break
    if close_idx is None:
        return None

    # Scan backwards for the matching open brace / struct tag
    brace_depth = 0
    for i in range(close_idx, -1, -1):
        brace_depth += lines[i].count('}') - lines[i].count('{')
        m = open_re.search(lines[i])
        if m and brace_depth >= 0:
            return m.group(1)
    return None

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
    """Run Gradle, stream output to stdout + log. Returns True on success."""
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) ...")
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

def _extract_incomplete_type(line):
    for pat in [r"\(aka 'struct ([^']+)'\)", r"'struct ([^']+)'", r"'([^']+)'"]:
        m = re.search(pat, line)
        if m:
            return m.group(1)
    return None

def classify_errors(log_data):
    cats = {
        "missing_n64_includes": [],
        "bad_fwd_injection":    [],   # (filepath, real_tag, wrong_tag, typedef_name)
        "local_struct_fwd":     [],
        "undefined_symbols":    [],
        "cmake_libraries":      False,
        "missing_sdk_types":    [],
        "missing_macros":       [],
        "static_conflict":      [],
        "incomplete_sizeof":    [],
        "daemon_crash":         False,
        "oom_detected":         False,
        "implicit_func":        [],
        "unknown_idents":       [],
    }

    local_struct_map = {}

    for line in log_data.splitlines():

        # Infrastructure failures
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

        # ── Typedef redefinition ────────────────────────────────────────────
        # Pattern: "typedef redefinition with different types ('struct REAL' vs 'struct INJECTED')"
        # The FIRST named group is the tag from the FILE's own definition.
        # The SECOND is what our AUTO block injected (the wrong guess).
        m_redef = re.search(
            r"typedef redefinition with different types \('struct ([^']+)' vs 'struct ([^']+)'\)",
            line
        )
        if m_redef and fp:
            real_tag   = m_redef.group(1)   # e.g. "ch_vegatable"
            wrong_tag  = m_redef.group(2)   # e.g. "chVegetable_s"
            # Check if this is OUR injection (wrong_tag ends with _s and file has AUTO block)
            if wrong_tag.endswith("_s") and os.path.exists(fp):
                content = read_file(fp)
                if AUTO_MARKER in content:
                    # Derive the typedef name from the wrong_tag (strip trailing _s)
                    # but we can recover it directly from the file's } NAME; line
                    typedef_name = wrong_tag[:-2]  # best guess; will be overridden below
                    # Try to find the actual typedef name from the file
                    close_m = re.search(r"\}\s*(\w+)\s*;", content)
                    if close_m:
                        typedef_name = close_m.group(1)
                    cats["bad_fwd_injection"].append((fp, real_tag, wrong_tag, typedef_name))
                    continue  # don't also log as unknown
            # Genuine redefinition not caused by us — log for awareness
            cats["unknown_idents"].append((fp, f"typedef_redef:{real_tag}"))
            continue

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
            if ident in KNOWN_GLOBAL_TYPES:
                cats["missing_sdk_types"].append(ident)
            elif ident in KNOWN_MACROS:
                cats["missing_macros"].append(ident)
            elif re.fullmatch(r"[a-z_][a-z0-9_]*", ident):
                # Likely a cascade variable error — skip, resolves with root fix
                pass
            else:
                cats["unknown_idents"].append((fp, ident))

        elif m_static and fp:
            cats["static_conflict"].append((fp, m_static.group(1)))

        elif m_unknown:
            t = m_unknown.group(1)
            if t in KNOWN_GLOBAL_TYPES:
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

def _already_defined(content, name):
    return (
        f"typedef struct {name}" in content
        or f"typedef {KNOWN_SDK_TYPEDEFS.get(name, '__never__')} {name};" in content
        or f"typedef unsigned int {name};" in content
        or f"#define {name}" in content
    )


def fix_bad_fwd_injections(cats):
    """FIX B — strip our bad AUTO block and re-inject with the correct struct tag.

    Scenario: fix_local_struct_fwd guessed 'struct chVegetable_s' for a typedef
    whose real definition uses 'struct ch_vegatable' (a typo in the source).
    Clang reports: typedef redefinition with different types.
    We recover by:
      1. Stripping our AUTO block from the file.
      2. Re-injecting a correct 'typedef struct REAL_TAG TYPEDEF_NAME;' only if
         the struct is NOT fully defined before its first use (i.e. it's a
         forward reference to a type defined later in the same file).
         If the full definition is already present, no forward decl is needed.
    """
    if not cats["bad_fwd_injection"]:
        return 0
    fixes = 0
    for fp, real_tag, wrong_tag, typedef_name in cats["bad_fwd_injection"]:
        if not os.path.exists(fp):
            continue
        content = read_file(fp)
        # Step 1: strip the AUTO block
        content, stripped = strip_auto_block(content)
        if not stripped:
            continue

        # Step 2: check if the struct is fully defined in this file.
        # If "struct REAL_TAG {" appears, the full definition is present —
        # a forward decl would be redundant and harmful if it uses a different tag.
        # Only re-inject if the typedef is used BEFORE the definition in the file
        # AND the definition is NOT at the top level (which would already cover it).
        full_def_re = re.compile(r"\bstruct\s+" + re.escape(real_tag) + r"\s*\{")
        has_full_def = bool(full_def_re.search(content))

        if has_full_def:
            # The struct is fully defined in the file. No forward decl needed.
            # Just remove our bad block — the compiler will see the full def.
            write_file(fp, content)
            print(f"  [B] Removed bad AUTO block from {os.path.basename(fp)} "
                  f"(struct '{real_tag}' is fully defined in file)")
        else:
            # Struct is defined elsewhere — inject a correct forward decl
            correct_fwd = f"typedef struct {real_tag} {typedef_name};"
            if correct_fwd not in content:
                content = AUTO_MARKER + "\n" + correct_fwd + "\n" + content
                print(f"  [B] Re-injected correct fwd decl: {correct_fwd}")
            write_file(fp, content)

        fixes += 1
    return fixes


def fix_missing_sdk_types(cats):
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


def fix_missing_macros(cats):
    """FIX M — inject #define constants into n64_types.h."""
    needed = set(cats["missing_macros"])
    to_inject = {k: v for k, v in KNOWN_MACROS.items() if k in needed}
    if not to_inject or not os.path.exists(TYPES_HEADER):
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


def fix_local_struct_fwd(cats):
    """FIX C — inject forward declarations for local game-logic structs.

    Improvement over the original: before guessing the struct tag, we scan
    the file for a matching '} TypedefName;' pattern and extract the real tag.
    This avoids the ch_vegatable/chVegetable_s mismatch class of errors.
    """
    if not cats["local_struct_fwd"]:
        return 0
    file_to_types = {}
    for fp, t in cats["local_struct_fwd"]:
        file_to_types.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, type_names in file_to_types.items():
        if not os.path.exists(fp):
            continue
        content = read_file(fp)
        new_decls = []
        for t in sorted(type_names):
            # First: try to find the real struct tag from the file's own definition
            real_tag = _real_struct_tag_for_typedef(content, t)
            if real_tag:
                fwd = f"typedef struct {real_tag} {t};"
            else:
                # Fallback: derive tag by convention (sChVegetable -> chVegetable_s)
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in "sS" else t
                fwd = f"typedef struct {tag}_s {t};"
            if fwd not in content and f"typedef struct" not in content.split(f"{t};")[0].split("\n")[-1]:
                new_decls.append(fwd)
        if new_decls:
            content = AUTO_MARKER + "\n" + "\n".join(new_decls) + "\n" + content
            write_file(fp, content)
            print(f"  [C] Injected fwd decls {sorted(type_names)} -> {os.path.basename(fp)}")
            fixes += 1
    return fixes


def fix_missing_n64_includes(cats):
    """FIX A — add force-include guard to source files missing n64_types.h."""
    fixes = 0
    for fp in set(cats["missing_n64_includes"]):
        if not os.path.exists(fp) or fp.endswith("n64_types.h"):
            continue
        content = read_file(fp)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(fp, '#include "ultra/n64_types.h"\n' + content)
            print(f"  [A] Added n64_types.h include -> {os.path.basename(fp)}")
            fixes += 1
    return fixes


def fix_cmake_libraries():
    """FIX J — ensure -lm -llog are linked."""
    if not os.path.exists(CMAKE_FILE):
        return 0
    cmake = read_file(CMAKE_FILE)
    if "target_link_libraries(" in cmake and " m " not in cmake:
        cmake = re.sub(r"(target_link_libraries\([^)]+)", r"\1 m log ", cmake)
        write_file(CMAKE_FILE, cmake)
        print("  [J] Injected -lm -llog into CMakeLists.txt")
        return 1
    return 0


def fix_undefined_symbols(cats):
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


def handle_oom(cats):
    """FIX O/D — bump heap on OOM; flag daemon crash as retryable."""
    global _HEAP_GB
    fixed = 0
    if cats["oom_detected"]:
        new_heap = min(_HEAP_GB + 2, 14)
        if new_heap != _HEAP_GB:
            print(f"  [O] Java OOM — raising heap {_HEAP_GB}g -> {new_heap}g")
            _HEAP_GB = new_heap
            fixed += 1
        else:
            print("  [O] Java OOM — heap at cap (14g); consider splitting the source set.")
    if cats["daemon_crash"]:
        print("  [D] Gradle daemon crash (likely daemon-JVM OOM). Retrying with --no-daemon.")
        fixed += 1
    return fixed


# ── Top-level dispatcher ─────────────────────────────────────────────────────

def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0
    log_data = read_file(LOG_FILE)
    cats = classify_errors(log_data)

    fixes = 0
    fixes += handle_oom(cats)
    fixes += fix_cmake_libraries()
    fixes += fix_bad_fwd_injections(cats)    # FIX B — must run before fix_local_struct_fwd
    fixes += fix_missing_sdk_types(cats)
    fixes += fix_missing_macros(cats)
    fixes += fix_local_struct_fwd(cats)
    fixes += fix_missing_n64_includes(cats)
    fixes += fix_undefined_symbols(cats)

    unknown = sorted(set(
        str(id_) for _, id_ in cats.get("unknown_idents", [])
        if not str(id_).startswith("typedef_redef:")
    ))
    if unknown:
        print(f"  [?] Unknown identifiers requiring manual investigation: {unknown}")

    return fixes


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    max_cycles = 100
    for i in range(1, max_cycles + 1):
        print(f"\n{'='*60}")
        print(f"  Build Cycle {i} / {max_cycles}")
        print(f"{'='*60}")

        if run_build():
            print("\n✅ Build Successful! APK is ready.")
            sys.exit(0)

        print("\n🔍 Analysing errors ...")
        applied = apply_fixes()

        if applied == 0:
            print("\n🛑 No fixable patterns detected. Manual intervention required.")
            print(f"   Check: {LOG_FILE}")
            sys.exit(1)

        print(f"\n  Applied {applied} fix(es). Retrying ...")
        time.sleep(1)

    print(f"\n🛑 Reached cycle limit ({max_cycles}). Build did not complete.")
    sys.exit(1)


if __name__ == "__main__":
    main()
