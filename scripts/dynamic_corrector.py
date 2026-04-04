"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Updates for Cycle 7:
  - Added 'Tag Learning': Extracts correct struct tags from "redefinition with different types" errors.
  - Added 'Block Refresher': Logic to update/overwrite previous [AUTO] injections if they are wrong.
  - Fixed JVM: Ensured '-XX:+HeapDumpOnOutOfMemoryError' is used correctly.
  - Hardened Classifier: Catches 'incomplete definition' and 'redefinition' specifically to 
    map symbols to their correct underlying struct tags.
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

# ── Utilities ────────────────────────────────────────────────────────────────

def read_file(path):
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    if path.endswith((".h", ".c", ".cpp")):
        if content.count('{') != content.count('}'):
            print(f"  [!] REJECTED: Brace mismatch in {os.path.basename(path)}")
            return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path):
    if not path: return None
    p_lower = path.lower()
    if any(x in p_lower for x in ["/usr/", "/ndk/", "toolchains", "include/2.0l"]):
        return None
    return path

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
        "tag_mismatch":         [],
        "local_struct_fwd":     [],
        "undefined_symbols":    [],
        "missing_sdk_types":    [],
        "missing_macros":       [],
        "oom_detected":         False,
    }

    local_struct_map = {}

    lines = log_data.splitlines()
    for i, line in enumerate(lines):
        if "OutOfMemoryError" in line: cats["oom_detected"] = True; continue
        if "error:" not in line and "note:" not in line: continue

        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)
        if not fp: continue

        # 1. Catch Tag Mismatches (redefinition with different types)
        # e.g. error: redefinition of 'sChVegetable' with different types ('struct ch_vegatable' vs 'struct sChVegetable_s')
        m_tag = re.search(r"redefinition of '([^']+)' with different types \('struct ([^']+)' vs 'struct ([^']+)'\)", line)
        if m_tag:
            cats["tag_mismatch"].append({
                "file": fp, "symbol": m_tag.group(1), "real_tag": m_tag.group(2)
            })
            continue

        # 2. Catch Unknown Types
        m_unknown = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        if m_unknown:
            t = m_unknown.group(1)
            if t in KNOWN_SDK_TYPEDEFS: cats["missing_sdk_types"].append(t)
            else: local_struct_map.setdefault(fp, set()).add(t)
            continue

        # 3. Catch Undefined Symbols (Linker)
        m_undef = re.search(r"(?:undefined symbol:|undefined reference to `)([^']+)'?", line)
        if m_undef:
            cats["undefined_symbols"].append(m_undef.group(1).strip("`' "))

    for fp, type_names in local_struct_map.items():
        for t in type_names: cats["local_struct_fwd"].append((fp, t))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def fix_tag_mismatches(cats):
    fixes = 0
    for item in cats["tag_mismatch"]:
        fp, sym, tag = item["file"], item["symbol"], item["real_tag"]
        content = read_file(fp)
        # Regex to find our previous bad injection
        old_pattern = rf"typedef struct \w+ {sym};"
        new_line = f"typedef struct {tag} {sym};"
        if re.search(old_pattern, content):
            new_content = re.sub(old_pattern, new_line, content)
            write_file(fp, new_content)
            print(f"  [T] Learned struct tag: {sym} -> struct {tag}")
            fixes += 1
    return fixes

def fix_local_struct_fwd(cats):
    file_to_types = {}
    for fp, t in cats["local_struct_fwd"]: file_to_types.setdefault(fp, set()).add(t)
    fixes = 0
    for fp, types in file_to_types.items():
        content = read_file(fp)
        new_decls = []
        for t in sorted(types):
            # Guard: check if definition exists later in file
            if f"struct {t} {{" in content or f"typedef struct" in content and f" {t};" in content:
                # We guess tag_s first, fix_tag_mismatches will correct it if compiler complains
                fwd = f"typedef struct {t}_s {t};"
                if fwd not in content and f" {t};" not in content:
                    new_decls.append(fwd)
        
        if new_decls:
            # Check for existing block to append to, or create new
            if AUTO_MARKER in content:
                parts = content.split(AUTO_MARKER)
                # Append new decls inside the existing block area
                parts[1] = "\n" + "\n".join(new_decls) + parts[1]
                write_file(fp, AUTO_MARKER.join(parts))
            else:
                write_file(fp, f"{AUTO_MARKER}\n" + "\n".join(new_decls) + "\n\n" + content)
            print(f"  [C] Fwd decls {list(types)} -> {os.path.basename(fp)}")
            fixes += 1
    return fixes

def fix_missing_sdk_types(cats):
    missing = set(cats["missing_sdk_types"])
    if not missing: return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(missing):
        if f" {t};" in content: continue
        content += f"\ntypedef {KNOWN_SDK_TYPEDEFS[t]} {t};\n"
        added = True
        print(f"  [K] Added SDK type: {t}")
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

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
    # Always ensure header guard
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            write_file(TYPES_HEADER, "#pragma once\n" + content)
            fixes += 1
    
    if cats["oom_detected"]: 
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    # Priority 1: Correct previous mistakes (Tag Mismatches)
    fixes += fix_tag_mismatches(cats)
    # Priority 2: Standard missing types/symbols
    fixes += fix_missing_sdk_types(cats)
    fixes += fix_local_struct_fwd(cats)
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
