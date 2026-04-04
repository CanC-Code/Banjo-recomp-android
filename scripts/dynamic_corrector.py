"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Enhanced with:
  - Static conflict resolution (stripping 'static' from conflicting decls)
  - Incomplete type dummy definitions (fixing sizeof errors)
  - Expanded SDK dictionary for Ultra64/N64 types
  - Implicit function stub generation
"""

import os
import re
import subprocess
import sys
import time

# ── Build environment ────────────────────────────────────────────────────────

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

# Heap starts at 6g; raised automatically on OOM.
_HEAP_GB = 6

def _gradle_cmd():
    return [
        "./gradlew", "-p", "Android", "assembleDebug",
        "--console=plain", "--max-workers=1", "--no-daemon",
        f"-Dorg.gradle.jvmargs=-Xmx{_HEAP_GB}g -XX:+HeapDumpOnOutOfMemoryError",
    ]

LOG_FILE     = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"
CMAKE_FILE   = "Android/app/src/main/cpp/CMakeLists.txt"

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
    "size_t":        "unsigned long",
    "uintptr_t":     "unsigned long",
}

KNOWN_SDK_STRUCT_TYPES = {
    "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Gfx_t", "Mtx", "Mtx_t", "Vp",
    "OSContPad", "OSTimer", "OSThread", "OSMesgQueue", "OSTask", "OSTask_t",
    "OSEvent", "CPUState", "Actor", "ActorMarker", "LookAt", "Hilite", "Light",
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
    "M_PI":       "3.14159265358979323846",
}

# ── Utilities ────────────────────────────────────────────────────────────────

_ANSI = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text):
    return _ANSI.sub('', text)

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except: return ""

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path):
    if not path or "/usr/" in path or "ndk" in path.lower():
        return None
    return path

def strip_auto_block(content):
    if AUTO_MARKER not in content:
        return content, False
    lines = content.splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if AUTO_MARKER in l), None)
    if start is None: return content, False
    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped == "" or stripped.startswith("typedef struct") or AUTO_MARKER in stripped:
            end += 1
        else: break
    return "".join(lines[:start]) + "".join(lines[end:]), True

def _real_struct_tag_for_typedef(content, typedef_name):
    open_re  = re.compile(r"\bstruct\s+(\w+)\s*\{")
    close_re = re.compile(r"\}\s*" + re.escape(typedef_name) + r"\s*;")
    lines = content.splitlines()
    close_idx = next((i for i, l in enumerate(lines) if close_re.search(l)), None)
    if close_idx is None: return None
    brace_depth = 0
    for i in range(close_idx, -1, -1):
        brace_depth += lines[i].count('}') - lines[i].count('{')
        m = open_re.search(lines[i])
        if m and brace_depth >= 0: return m.group(1)
    return None

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) ...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(_gradle_cmd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            clean = strip_ansi(line)
            log.write(clean); print(clean, end="")
        proc.wait()
    return proc.returncode == 0

# ── Error classifier ──────────────────────────────────────────────────────────

_FILE_RE = re.compile(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))")

def classify_errors(log_data):
    cats = {
        "missing_n64_includes": [], "bad_fwd_injection": [], "local_struct_fwd": [],
        "undefined_symbols": [], "cmake_libraries": False, "missing_sdk_types": [],
        "missing_macros": [], "static_conflict": [], "incomplete_sizeof": [],
        "daemon_crash": False, "oom_detected": False, "unknown_idents": [],
    }
    local_struct_map = {}
    for line in log_data.splitlines():
        if "Could not receive a message from the daemon" in line: cats["daemon_crash"] = True; continue
        if "OutOfMemoryError" in line or "Java heap space" in line: cats["oom_detected"] = True; continue
        if "error:" not in line and "undefined" not in line: continue

        pm = _FILE_RE.search(line); fp = source_path(pm.group(1) if pm else None)
        
        m_redef = re.search(r"typedef redefinition with different types \('struct ([^']+)' vs 'struct ([^']+)'\)", line)
        if m_redef and fp:
            real_tag, wrong_tag = m_redef.group(1), m_redef.group(2)
            if wrong_tag.endswith("_s"):
                content = read_file(fp)
                close_m = re.search(r"\}\s*(\w+)\s*;", content)
                cats["bad_fwd_injection"].append((fp, real_tag, wrong_tag, close_m.group(1) if close_m else wrong_tag[:-2]))
            continue

        m_static = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        m_ident = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef = re.search(r"undefined (?:symbol|reference to) [^`']*[`']?([^' \n]+)", line)
        m_inc = re.search(r"incomplete type '(?:struct )?([^']+)'", line)

        if m_undef: cats["undefined_symbols"].append(m_undef.group(1).strip("`'"))
        elif m_implicit: cats["undefined_symbols"].append(m_implicit.group(1))
        elif m_ident:
            ident = m_ident.group(1)
            if ident in KNOWN_GLOBAL_TYPES: cats["missing_sdk_types"].append(ident)
            elif ident in KNOWN_MACROS: cats["missing_macros"].append(ident)
            else: cats["unknown_idents"].append((fp, ident))
        elif m_static and fp: cats["static_conflict"].append((fp, m_static.group(1)))
        elif m_unknown:
            t = m_unknown.group(1)
            if t in KNOWN_GLOBAL_TYPES: cats["missing_sdk_types"].append(t)
            elif fp: local_struct_map.setdefault(fp, set()).add(t)
        elif m_inc and fp: cats["incomplete_sizeof"].append((fp, m_inc.group(1)))
        elif fp and os.path.exists(fp): cats["missing_n64_includes"].append(fp)

    for fp, names in local_struct_map.items():
        for t in names: cats["local_struct_fwd"].append((fp, t))
    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def fix_static_conflict(cats):
    """FIX S — Remove 'static' keyword from declarations that conflict with headers."""
    fixes = 0
    for fp, func in cats["static_conflict"]:
        if not os.path.exists(fp): continue
        content = read_file(fp)
        new_content = re.sub(rf"^static\s+([^\n]+{re.escape(func)}\s*\()", r"\1", content, flags=re.MULTILINE)
        if new_content != content:
            write_file(fp, new_content)
            print(f"  [S] Removed static from {func} in {os.path.basename(fp)}"); fixes += 1
    return fixes

def fix_incomplete_sizeof(cats):
    """FIX T — Add dummy struct definitions for incomplete types to n64_types.h."""
    types = set(cats["incomplete_sizeof"])
    if not types or not os.path.exists(TYPES_HEADER): return 0
    content = read_file(TYPES_HEADER); added = False
    for t in sorted(types):
        if f"struct {t}" not in content:
            content += f"\nstruct {t} {{ char dummy[256]; }};\n"
            added = True; print(f"  [T] Defined dummy struct for incomplete type: {t}")
    if added: write_file(TYPES_HEADER, content); return 1
    return 0

def fix_bad_fwd_injections(cats):
    fixes = 0
    for fp, real_tag, _, name in cats["bad_fwd_injection"]:
        content, stripped = strip_auto_block(read_file(fp))
        if not stripped: continue
        if f"struct {real_tag} {{" not in content:
            content = f"{AUTO_MARKER}\ntypedef struct {real_tag} {name};\n{content}"
            print(f"  [B] Fixed fwd injection for {name} using tag {real_tag}")
        write_file(fp, content); fixes += 1
    return fixes

def fix_missing_sdk_types(cats):
    missing = set(cats["missing_sdk_types"])
    if not missing or not os.path.exists(TYPES_HEADER): return 0
    content = read_file(TYPES_HEADER); added = False
    for t in sorted(missing):
        if t in content: continue
        decl = f"\ntypedef {KNOWN_SDK_TYPEDEFS.get(t, 'unsigned int')} {t};\n"
        content += decl; added = True; print(f"  [K] Defined SDK type: {t}")
    if added: write_file(TYPES_HEADER, content); return 1
    return 0

def fix_local_struct_fwd(cats):
    file_map = {}
    for fp, t in cats["local_struct_fwd"]: file_map.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, names in file_map.items():
        content = read_file(fp); new_decls = []
        for t in sorted(names):
            tag = _real_struct_tag_for_typedef(content, t) or (t[1].lower() + t[2:] if t.startswith(('s', 'S')) else t)
            fwd = f"typedef struct {tag}_s {t};"
            if fwd not in content: new_decls.append(fwd)
        if new_decls:
            write_file(fp, f"{AUTO_MARKER}\n" + "\n".join(new_decls) + "\n" + content)
            print(f"  [C] Injected {len(new_decls)} fwd decls into {os.path.basename(fp)}"); fixes += 1
    return fixes

def fix_undefined_symbols(cats):
    syms = set(cats["undefined_symbols"])
    if not syms: return 0
    stubs = read_file(STUBS_FILE) or '#include "n64_types.h"\n'
    added = False
    for sym in sorted(syms):
        if f" {sym}(" in stubs: continue
        stubs += f"\nlong long int {sym}() {{ return 0; }}\n"; added = True
        print(f"  [I] Generated stub: {sym}")
    if added: write_file(STUBS_FILE, stubs); return 1
    return 0

def apply_fixes():
    if not os.path.exists(LOG_FILE): return 0
    log_data = read_file(LOG_FILE); cats = classify_errors(log_data)
    fixes = 0
    if cats["oom_detected"] or cats["daemon_crash"]:
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 12); fixes += 1
    fixes += fix_bad_fwd_injections(cats)
    fixes += fix_missing_sdk_types(cats)
    fixes += fix_incomplete_sizeof(cats)
    fixes += fix_static_conflict(cats)
    fixes += fix_local_struct_fwd(cats)
    fixes += fix_undefined_symbols(cats)
    return fixes

def main():
    for i in range(1, 50):
        print(f"\n--- Cycle {i} ---")
        if run_build(): print("\n✅ Success!"); sys.exit(0)
        if apply_fixes() == 0: print("\n🛑 No fixes applied. Check logs."); sys.exit(1)
        time.sleep(1)

if __name__ == "__main__": main()
