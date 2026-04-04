"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Fixes applied:
  - Resolved NameError for fix_missing_macros.
  - Harmonized static_conflict and redefinition logic (fixes the 'close' error).
  - Added OSHWIntr and audio state types (RESAMPLE_STATE, etc.) to known types.
  - Improved source_path to prevent filtering out internal project headers.
"""

import os
import re
import subprocess
import sys
import time

# ── Build environment ────────────────────────────────────────────────────────

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

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

AUTO_MARKER = "/* AUTO: forward declarations */"

# ── Type & Macro Definitions ─────────────────────────────────────────────────

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
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", # Audio states from synthInternals.h
}

KNOWN_GLOBAL_TYPES = set(KNOWN_SDK_TYPEDEFS) | KNOWN_SDK_STRUCT_TYPES

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
    p_lower = path.lower()
    # Don't touch system headers or NDK files
    if p_lower.startswith("/usr/") or "/ndk/" in p_lower or "toolchains" in p_lower:
        return None
    return path

def strip_auto_block(content):
    if AUTO_MARKER not in content:
        return content, False
    lines = content.splitlines(keepends=True)
    new_lines = []
    in_block = False
    for line in lines:
        if AUTO_MARKER in line:
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if stripped == "" or stripped.startswith("typedef struct"):
                continue
            else:
                in_block = False
        new_lines.append(line)
    return "".join(new_lines), True

def _real_struct_tag_for_typedef(content, typedef_name):
    close_re = re.compile(r"\}\s*" + re.escape(typedef_name) + r"\s*;")
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if close_re.search(line):
            depth = 0
            for j in range(i, -1, -1):
                depth += lines[j].count('}') - lines[j].count('{')
                if depth >= 0:
                    tag_m = re.search(r"struct\s+(\w+)", lines[j])
                    if tag_m: return tag_m.group(1)
    return None

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) ...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            _gradle_cmd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
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
        "redefinition":         [], # Renaming fix bucket
        "oom_detected":         False,
        "daemon_crash":         False,
    }

    local_struct_map = {}

    for line in log_data.splitlines():
        if "OutOfMemoryError" in line: cats["oom_detected"] = True; continue
        if "error:" not in line and "undefined" not in line: continue

        pm = _FILE_RE.search(line)
        fp = source_path(pm.group(1) if pm else None)

        # REDEFINITION / STATIC SHADOWING (e.g. 'close' vs unistd.h)
        m_redef = re.search(r"redefinition of '([^']+)'", line)
        m_shadow = re.search(r"static declaration of '([^']+)' follows non-static", line)
        if (m_redef or m_shadow) and fp:
            sym = (m_redef or m_shadow).group(1)
            cats["redefinition"].append((fp, sym))
            continue

        # TYPEDEF MISMATCH
        m_redef_t = re.search(r"typedef redefinition .* \('struct ([^']+)' vs 'struct ([^']+)'\)", line)
        if m_redef_t and fp:
            cats["bad_fwd_injection"].append((fp, m_redef_t.group(1), m_redef_t.group(2)))
            continue

        m_unknown = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        m_ident   = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_undef   = re.search(r"(?:undefined symbol:|undefined reference to `)([^']+)'?", line)

        if m_undef:
            cats["undefined_symbols"].append(m_undef.group(1).strip("`' "))
        elif m_ident:
            ident = m_ident.group(1)
            if ident in KNOWN_GLOBAL_TYPES: cats["missing_sdk_types"].append(ident)
            elif ident in KNOWN_MACROS: cats["missing_macros"].append(ident)
        elif m_unknown:
            t = m_unknown.group(1)
            if t in KNOWN_GLOBAL_TYPES: cats["missing_sdk_types"].append(t)
            elif fp: local_struct_map.setdefault(fp, set()).add(t)
        elif fp and 'include "ultra/n64_types.h"' not in read_file(fp):
            if fp.endswith(('.c', '.cpp')):
                cats["missing_n64_includes"].append(fp)

    for fp, type_names in local_struct_map.items():
        for t in type_names:
            cats["local_struct_fwd"].append((fp, t))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def fix_redefinitions(cats):
    """FIX R — Prepend renaming macros to resolve name collisions with system headers."""
    fixes = 0
    # Conflict list based on Android NDK's unistd.h and others
    SYSTEM_CONFLICTS = {"close", "read", "write", "open", "pipe", "index", "log"}
    
    for fp, sym in cats["redefinition"]:
        if sym in SYSTEM_CONFLICTS:
            content = read_file(fp)
            macro = f"#define {sym} game_{sym}"
            if macro not in content:
                # Prepend to the file to ensure all declarations are covered
                write_file(fp, f"{macro}\n" + content)
                print(f"  [R] Renamed conflicting symbol '{sym}' in {os.path.basename(fp)}")
                fixes += 1
    return fixes

def fix_missing_sdk_types(cats):
    missing = set(cats["missing_sdk_types"])
    if not missing or not os.path.exists(TYPES_HEADER): return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(missing):
        if f" {t};" in content or f" {t} " in content: continue
        if t in KNOWN_SDK_TYPEDEFS:
            decl = f"\ntypedef {KNOWN_SDK_TYPEDEFS[t]} {t};\n"
        else:
            decl = f"\ntypedef struct {t}_s {{ long long int res[16]; }} {t};\n"
        content += decl
        added = True
        print(f"  [K] Added SDK type: {t}")
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
        print(f"  [M] Injected macro: {macro}")
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

def fix_local_struct_fwd(cats):
    file_to_types = {}
    for fp, t in cats["local_struct_fwd"]:
        file_to_types.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, types in file_to_types.items():
        content = read_file(fp)
        new_decls = []
        for t in sorted(types):
            real_tag = _real_struct_tag_for_typedef(content, t)
            tag = real_tag if real_tag else (t[1:] if t.startswith('s') and t[1].isupper() else t)
            fwd = f"typedef struct {tag} {t};"
            if fwd not in content: new_decls.append(fwd)
        if new_decls:
            content, _ = strip_auto_block(content)
            write_file(fp, f"{AUTO_MARKER}\n" + "\n".join(new_decls) + "\n" + content)
            print(f"  [C] Fwd decls {list(types)} -> {os.path.basename(fp)}")
            fixes += 1
    return fixes

def fix_bad_fwd_injections(cats):
    fixes = 0
    for fp, real_tag, wrong_tag in cats["bad_fwd_injection"]:
        content, _ = strip_auto_block(read_file(fp))
        typedef_name = wrong_tag[:-2] if wrong_tag.endswith("_s") else wrong_tag
        if f"struct {real_tag} {{" not in content:
            write_file(fp, f"{AUTO_MARKER}\ntypedef struct {real_tag} {typedef_name};\n{content}")
        else:
            write_file(fp, content)
        fixes += 1
        print(f"  [B] Corrected fwd tag '{real_tag}' in {os.path.basename(fp)}")
    return fixes

def fix_missing_n64_includes(cats):
    fixes = 0
    for fp in set(cats["missing_n64_includes"]):
        content = read_file(fp)
        write_file(fp, '#include "ultra/n64_types.h"\n' + content)
        print(f"  [A] Added n64_types.h -> {os.path.basename(fp)}")
        fixes += 1
    return fixes

def fix_undefined_symbols(cats):
    syms = set(cats["undefined_symbols"])
    if not syms: return 0
    stubs = read_file(STUBS_FILE) or '#include "n64_types.h"\n'
    added = False
    for sym in sorted(syms):
        if f" {sym}(" in stubs: continue
        stubs += f"\nlong long int {sym}() {{ return 0; }}\n"
        added = True
        print(f"  [I] Stubbed: {sym}")
    if added: write_file(STUBS_FILE, stubs)
    return 1 if added else 0

# ── Dispatcher ───────────────────────────────────────────────────────────────

def apply_fixes():
    log_data = read_file(LOG_FILE)
    if not log_data: return 0
    cats = classify_errors(log_data)
    
    fixes = 0
    if cats["oom_detected"]: 
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    fixes += fix_redefinitions(cats)
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
            print("\n🛑 No further fixable patterns detected."); sys.exit(1)
        
        print(f"\n  Applied {applied} fixes. Retrying build...")
        time.sleep(1)

if __name__ == "__main__":
    main()
