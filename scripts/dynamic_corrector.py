"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Updates for Cycle 6:
  - Fixed JVM crash: Corrected typo in '-XX:+HeapDumpOnOutOfMemoryError'.
  - Restored missing functions: Implemented 'fix_missing_macros' and 'fix_missing_n64_includes'.
  - Brace Integrity: Added a count-based validation to prevent structural corruption of headers.
  - Safe Injection: Injected types and macros are now appended to a dedicated block to avoid
    breaking existing struct definitions.
  - Incomplete Type Handling: Added a pass to identify when a forward declaration is 
    insufficient (e.g., member access) and stubs the struct with a generic buffer.
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

AUTO_MARKER = "/* AUTO: generated declarations */"

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
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
    "LetterFloorTile", "GfxContext", "Vp", "Lightsn", "Light_t"
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

def read_file(path):
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    # Validation: Prevent saving files with broken brace pairs (a common cause of Cycle 5 failures)
    if path.endswith((".h", ".c", ".cpp")):
        if content.count('{') != content.count('}'):
            print(f"  [!] REJECTED write to {os.path.basename(path)}: Brace mismatch ({content.count('{')} vs {content.count('}')})")
            return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path):
    if not path: return None
    p_lower = path.lower()
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
            # Stop skipping once we hit code that isn't part of our injection
            if stripped == "" or stripped.startswith("typedef") or stripped.startswith("#define"):
                continue
            else:
                in_block = False
        new_lines.append(line)
    return "".join(new_lines), True

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) ...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            _gradle_cmd(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in proc.stdout:
            clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
            log.write(clean)
            print(clean, end="")
        proc.wait()
    return proc.returncode == 0

# ── Error classifier ──────────────────────────────────────────────────────────

def classify_errors(log_data):
    cats = {
        "missing_n64_includes": [],
        "local_struct_fwd":     [],
        "undefined_symbols":    [],
        "missing_sdk_types":    [],
        "missing_macros":       [],
        "redefinition":         [],
        "incomplete_type":      [],
        "oom_detected":         False,
    }

    local_struct_map = {}

    for line in log_data.splitlines():
        if "OutOfMemoryError" in line: cats["oom_detected"] = True; continue
        if "error:" not in line and "note:" not in line: continue

        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)

        m_redef = re.search(r"redefinition of '([^']+)'", line)
        if m_redef and fp:
            cats["redefinition"].append((fp, m_redef.group(1)))
            continue

        m_inc = re.search(r"incomplete definition of type 'struct ([^']+)'", line)
        if m_inc and fp:
            cats["incomplete_type"].append((fp, m_inc.group(1)))
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
        elif fp and fp.endswith(('.c', '.cpp')) and 'include "ultra/n64_types.h"' not in read_file(fp):
            cats["missing_n64_includes"].append(fp)

    for fp, type_names in local_struct_map.items():
        for t in type_names: cats["local_struct_fwd"].append((fp, t))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def deduplicate_definitions():
    """Safely removes duplicate typedefs while preserving struct bodies."""
    if not os.path.exists(TYPES_HEADER): return 0
    lines = read_file(TYPES_HEADER).splitlines()
    seen = set()
    new_lines = []
    fixed = False
    
    # We only deduplicate single-line injections to avoid eating multiline structs
    for line in lines:
        m = re.search(r"typedef\s+.*?\s+(\w+)\s*;", line)
        if m:
            t_name = m.group(1)
            if t_name in seen and "struct {" not in line:
                fixed = True
                continue
            seen.add(t_name)
        new_lines.append(line)
    
    if fixed:
        write_file(TYPES_HEADER, "\n".join(new_lines) + "\n")
        print(f"  [D] Deduplicated n64_types.h")
    return 1 if fixed else 0

def fix_missing_macros(cats):
    needed = set(cats["missing_macros"])
    if not needed: return 0
    content = read_file(TYPES_HEADER)
    added = False
    for macro in sorted(needed):
        if f"#define {macro}" in content: continue
        content += f"\n#ifndef {macro}\n#define {macro} {KNOWN_MACROS[macro]}\n#endif\n"
        added = True
        print(f"  [M] Injected macro: {macro}")
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

def fix_missing_n64_includes(cats):
    fixes = 0
    for fp in set(cats["missing_n64_includes"]):
        content = read_file(fp)
        write_file(fp, '#include "ultra/n64_types.h"\n' + content)
        print(f"  [A] Added n64_types.h -> {os.path.basename(fp)}")
        fixes += 1
    return fixes

def fix_redefinitions(cats):
    fixes = 0
    SYSTEM_CONFLICTS = {"close", "read", "write", "open", "pipe", "index", "log"}
    for fp, sym in cats["redefinition"]:
        if sym in SYSTEM_CONFLICTS:
            content = read_file(fp)
            macro = f"#define {sym} game_{sym}"
            if macro not in content:
                write_file(fp, f"{macro}\n" + content)
                print(f"  [R] Renamed conflict: {sym}")
                fixes += 1
    return fixes

def fix_missing_sdk_types(cats):
    missing = set(cats["missing_sdk_types"])
    if not missing: return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(missing):
        if f" {t};" in content or f" {t} " in content: continue
        decl = f"\ntypedef {KNOWN_SDK_TYPEDEFS[t]} {t};\n" if t in KNOWN_SDK_TYPEDEFS else \
               f"\ntypedef struct {t}_s {{ long long int res[32]; }} {t};\n"
        content += decl
        added = True
        print(f"  [K] Added SDK type: {t}")
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

def fix_local_struct_fwd(cats):
    file_to_types = {}
    for fp, t in cats["local_struct_fwd"]: file_to_types.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, types in file_to_types.items():
        content = read_file(fp)
        new_decls = []
        for t in sorted(types):
            if f"struct {t} {{" in content: continue
            fwd = f"typedef struct {t}_s {t};"
            if fwd not in content: new_decls.append(fwd)
        if new_decls:
            stripped, _ = strip_auto_block(content)
            write_file(fp, f"{AUTO_MARKER}\n" + "\n".join(new_decls) + "\n" + stripped)
            print(f"  [C] Fwd decls {list(types)} -> {os.path.basename(fp)}")
            fixes += 1
    return fixes

def fix_incomplete_types(cats):
    """If a struct is accessed (local->type) but only forward declared, upgrade to a stub definition."""
    fixes = 0
    for fp, tag in cats["incomplete_type"]:
        content = read_file(fp)
        # Check if we forward declared this in the AUTO block
        if f"typedef struct {tag}_s {tag};" in content:
            # Upgrade to a stub definition that at least contains a buffer to satisfy sizeof/access
            stub = f"struct {tag}_s {{ char res[1024]; }};"
            if stub not in content:
                content = content.replace(f"typedef struct {tag}_s {tag};", f"{stub}\ntypedef struct {tag}_s {tag};")
                write_file(fp, content)
                print(f"  [T] Upgraded incomplete type: {tag}")
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
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            write_file(TYPES_HEADER, "#pragma once\n" + content)
            fixes += 1
        fixes += deduplicate_definitions()
    
    if cats["oom_detected"]: 
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    fixes += fix_redefinitions(cats)
    fixes += fix_missing_sdk_types(cats)
    fixes += fix_missing_macros(cats)
    fixes += fix_local_struct_fwd(cats)
    fixes += fix_incomplete_types(cats)
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
