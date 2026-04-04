"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Cycle logic:
  1. Run Gradle / ninja build, stream output to log.
  2. Parse the log for every known error pattern.
  3. Apply targeted fixes to source / headers.
  4. Repeat until the build succeeds or no new fixes can be applied.

Error taxonomy handled:
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
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path):
    if not path: return None
    if "/usr/" in path or "ndk" in path.lower(): return None
    return path

def strip_auto_block(content):
    if AUTO_MARKER not in content:
        return content, False
    lines = content.splitlines(keepends=True)
    start, end = None, None
    for i, line in enumerate(lines):
        if AUTO_MARKER in line:
            start = i
            break
    if start is None: return content, False
    
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
    open_re  = re.compile(r"\bstruct\s+(\w+)\s*\{")
    close_re = re.compile(r"\}\s*" + re.escape(typedef_name) + r"\s*;")
    lines = content.splitlines()
    close_idx = None
    for i, line in enumerate(lines):
        if close_re.search(line):
            close_idx = i
            break
    if close_idx is None: return None

    brace_depth = 0
    for i in range(close_idx, -1, -1):
        brace_depth += lines[i].count('}') - lines[i].count('{')
        m = open_re.search(lines[i])
        if m and brace_depth >= 0:
            return m.group(1)
    return None

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
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

def classify_errors(log_data):
    cats = {
        "missing_n64_includes": [],
        "bad_fwd_injection":    [],   
        "local_struct_fwd":     [],
        "undefined_symbols":    [],
        "cmake_libraries":      False,
        "missing_sdk_types":    [],
        "missing_macros":       [],
        "static_conflict":      [],
        "incomplete_sizeof":    [],
        "daemon_crash":         False,
        "oom_detected":         False,
        "unknown_idents":       [],
    }

    local_struct_map = {}

    for line in log_data.splitlines():
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

        m_redef = re.search(r"typedef redefinition with different types \('struct ([^']+)' vs 'struct ([^']+)'\)", line)
        if m_redef and fp:
            real_tag, wrong_tag = m_redef.group(1), m_redef.group(2)
            if wrong_tag.endswith("_s") and os.path.exists(fp):
                content = read_file(fp)
                if AUTO_MARKER in content:
                    close_m = re.search(r"\}\s*(\w+)\s*;", content)
                    typedef_name = close_m.group(1) if close_m else wrong_tag[:-2]
                    cats["bad_fwd_injection"].append((fp, real_tag, wrong_tag, typedef_name))
                    continue

        m_static   = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown  = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        m_ident    = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_undef_s  = re.search(r"undefined symbol: (.*)", line)
        m_undef_r  = re.search(r"undefined reference to `([^']+)'", line)
        
        if m_undef_s or m_undef_r:
            sym = (m_undef_s or m_undef_r).group(1).strip("`' ")
            cats["undefined_symbols"].append(sym)
        elif m_ident:
            ident = m_ident.group(1)
            if ident in KNOWN_GLOBAL_TYPES: cats["missing_sdk_types"].append(ident)
            elif ident in KNOWN_MACROS: cats["missing_macros"].append(ident)
            else: cats["unknown_idents"].append((fp, ident))
        elif m_static and fp:
            cats["static_conflict"].append((fp, m_static.group(1)))
        elif m_unknown:
            t = m_unknown.group(1)
            if t in KNOWN_GLOBAL_TYPES: cats["missing_sdk_types"].append(t)
            elif fp: local_struct_map.setdefault(fp, set()).add(t)
        elif "incomplete type" in line and fp:
            m_inc = re.search(r"'struct ([^']+)'", line)
            if m_inc: cats["incomplete_sizeof"].append((fp, m_inc.group(1)))
        elif fp and os.path.exists(fp) and "error:" in line:
            if 'include "ultra/n64_types.h"' not in read_file(fp):
                cats["missing_n64_includes"].append(fp)

    for fp, type_names in local_struct_map.items():
        for t in type_names:
            cats["local_struct_fwd"].append((fp, t))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def fix_bad_fwd_injections(cats):
    if not cats["bad_fwd_injection"]: return 0
    fixes = 0
    for fp, real_tag, wrong_tag, typedef_name in cats["bad_fwd_injection"]:
        content, stripped = strip_auto_block(read_file(fp))
        if not stripped: continue
        if bool(re.search(r"\bstruct\s+" + re.escape(real_tag) + r"\s*\{", content)):
            write_file(fp, content)
        else:
            write_file(fp, f"{AUTO_MARKER}\ntypedef struct {real_tag} {typedef_name};\n{content}")
        fixes += 1
    return fixes

def fix_missing_sdk_types(cats):
    missing = set(cats["missing_sdk_types"])
    if not missing or not os.path.exists(TYPES_HEADER): return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(missing):
        if f"typedef struct {t}" in content or f"typedef unsigned int {t}" in content: continue
        decl = f"\ntypedef {KNOWN_SDK_TYPEDEFS[t]} {t};\n" if t in KNOWN_SDK_TYPEDEFS else \
               f"\ntypedef struct {t}_s {{ long long int reserved[64]; }} {t};\n"
        content += decl
        added = True
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

def fix_missing_macros(cats):
    needed = set(cats["missing_macros"])
    to_inject = {k: v for k, v in KNOWN_MACROS.items() if k in needed}
    if not to_inject or not os.path.exists(TYPES_HEADER): return 0
    content = read_file(TYPES_HEADER)
    added = False
    for macro, value in sorted(to_inject.items()):
        if f"#define {macro}" in content: continue
        content += f"\n#ifndef {macro}\n#define {macro} {value}\n#endif\n"
        added = True
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

def fix_local_struct_fwd(cats):
    if not cats["local_struct_fwd"]: return 0
    file_to_types = {}
    for fp, t in cats["local_struct_fwd"]: file_to_types.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, type_names in file_to_types.items():
        content = read_file(fp)
        new_decls = []
        for t in sorted(type_names):
            real_tag = _real_struct_tag_for_typedef(content, t)
            tag = real_tag if real_tag else (t[1:] if t.startswith('s') else t)
            fwd = f"typedef struct {tag} {t};"
            if fwd not in content: new_decls.append(fwd)
        if new_decls:
            content = f"{AUTO_MARKER}\n" + "\n".join(new_decls) + "\n" + content
            write_file(fp, content)
            fixes += 1
    return fixes

def fix_missing_n64_includes(cats):
    fixes = 0
    for fp in set(cats["missing_n64_includes"]):
        content = read_file(fp)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(fp, '#include "ultra/n64_types.h"\n' + content)
            fixes += 1
    return fixes

def fix_cmake_libraries():
    if not os.path.exists(CMAKE_FILE): return 0
    cmake = read_file(CMAKE_FILE)
    if "target_link_libraries(" in cmake and " m " not in cmake:
        cmake = re.sub(r"(target_link_libraries\([^)]+)", r"\1 m log ", cmake)
        write_file(CMAKE_FILE, cmake)
        return 1
    return 0

def fix_undefined_symbols(cats):
    syms = set(cats["undefined_symbols"])
    if not syms: return 0
    stubs = read_file(STUBS_FILE) or '#include "n64_types.h"\n\n'
    added = False
    for sym in sorted(syms):
        if f" {sym}(" in stubs: continue
        stubs += f"\nlong long int {sym}() {{ return 0; }}\n"
        added = True
    if added: write_file(STUBS_FILE, stubs)
    return 1 if added else 0

def handle_oom(cats):
    global _HEAP_GB
    if cats["oom_detected"]:
        new_heap = min(_HEAP_GB + 2, 14)
        if new_heap != _HEAP_GB:
            _HEAP_GB = new_heap
            return 1
    return 1 if cats["daemon_crash"] else 0

# ── Top-level dispatcher ─────────────────────────────────────────────────────

def apply_fixes():
    log_data = read_file(LOG_FILE)
    if not log_data: return 0
    cats = classify_errors(log_data)
    fixes = 0
    fixes += handle_oom(cats)
    fixes += fix_cmake_libraries()
    fixes += fix_bad_fwd_injections(cats)
    fixes += fix_missing_sdk_types(cats)
    fixes += fix_missing_macros(cats)
    fixes += fix_local_struct_fwd(cats)
    fixes += fix_missing_n64_includes(cats)
    fixes += fix_undefined_symbols(cats)
    return fixes

def main():
    for i in range(1, 101):
        print(f"\n{'='*60}\n  Build Cycle {i}\n{'='*60}")
        if run_build():
            print("\n✅ Build Successful!"); sys.exit(0)
        applied = apply_fixes()
        if applied == 0:
            print("\n🛑 No fixes possible. Check logs."); sys.exit(1)
        print(f"\n  Applied {applied} fix(es). Retrying...")
        time.sleep(1)

if __name__ == "__main__":
    main()
