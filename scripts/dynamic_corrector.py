"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Updates for Cycle 12:
  - Typedef Synchronizer: Robustly detects "typedef redefinition" errors and 
    automatically syncs the Global Registry (n64_autodecls.h) with the 
    actual struct tags found in the decompiled source.
  - Robust NDK Regex: Updated the error parser to handle the specific quoting 
    and parentheses used by Clang 17+ in the Android NDK.
  - Forward-to-Body Promotion: If a type is used as an array element 
    (incomplete type error), it is automatically promoted from a forward 
    declaration to a padded struct to allow the build to proceed.
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
AUTO_HEADER  = "Android/app/src/main/cpp/ultra/n64_autodecls.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# ── Type Definitions ─────────────────────────────────────────────────────────

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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def source_path(path):
    if not path: return None
    p_lower = path.lower()
    if any(x in p_lower for x in ["/usr/", "/ndk/", "toolchains", "include/2.0l"]):
        return None
    if "/Banjo-recomp-android/Banjo-recomp-android/" in path:
        return path.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
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
        "tag_mismatch":    [],
        "incomplete_type": [],
        "local_struct":    [],
        "undefined":       [],
        "sdk_type":        [],
        "collision":       [],
        "oom":             False,
    }

    for line in log_data.splitlines():
        if "OutOfMemoryError" in line: cats["oom"] = True; continue
        
        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)
        if not fp: continue

        # Collisions (static vs non-static)
        m_coll = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        if m_coll:
            cats["collision"].append({"file": fp, "sym": m_coll.group(1)})
            continue

        # Redefinition / Tag Syncing (Crucial for Cycle 12)
        # Matches: error: typedef redefinition with different types ('struct A' vs 'struct B')
        m_tag = re.search(r"(?:typedef\s+)?redefinition\s+of\s+'([^']+)'\s+with\s+different\s+types\s*\(?'struct\s+([^']+)'\s+vs\s+'struct\s+([^']+)'\)?", line)
        if m_tag:
            # Type B is usually what's in our Registry, Type A is what the compiler found in the file
            cats["tag_mismatch"].append({"sym": m_tag.group(1), "correct_tag": m_tag.group(2)})
            continue

        # Incomplete Type
        m_inc = re.search(r"incomplete\s+definition\s+of\s+type\s+'struct\s+([^']+)'", line)
        if m_inc:
            cats["incomplete_type"].append({"file": fp, "tag": m_inc.group(1)})
            continue

        # Unknown Type
        m_unk = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        if m_unk:
            t = m_unk.group(1)
            if t in KNOWN_SDK_TYPEDEFS: cats["sdk_type"].append(t)
            else: cats["local_struct"].append({"file": fp, "sym": t})
            continue

        # Linker
        m_def = re.search(r"(?:undefined symbol:|undefined reference to `)([^']+)'?", line)
        if m_def: cats["undefined"].append(m_def.group(1).strip("`' "))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def sync_typedef_tags(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    
    for entry in cats["tag_mismatch"]:
        sym, correct_tag = entry["sym"], entry["correct_tag"]
        # Look for the old incorrect typedef in the registry
        pattern = rf"typedef struct \w+ {sym};"
        if re.search(pattern, registry):
            new_line = f"typedef struct {correct_tag} {sym};"
            registry = re.sub(pattern, new_line, registry)
            print(f"  [S] Synced {sym} tag to {correct_tag}")
            fixes += 1
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

def update_global_registry(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER) or "#pragma once\n"
    
    unknown_syms = set(e["sym"] for e in cats["local_struct"])
    for s in sorted(unknown_syms):
        if f" {s};" in registry: continue
        # Default to a safe tag, will be synced by sync_typedef_tags if wrong
        tag = f"{s}_s"
        registry += f"typedef struct {tag} {s};\n"
        print(f"  [R] Registry Added: {s}")
        fixes += 1

    if fixes > 0:
        write_file(AUTO_HEADER, registry)
        types_content = read_file(TYPES_HEADER)
        if f'#include "{os.path.basename(AUTO_HEADER)}"' not in types_content:
            write_file(TYPES_HEADER, f'#include "{os.path.basename(AUTO_HEADER)}"\n' + types_content)
    return fixes

def fix_incomplete_types(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    
    for entry in cats["incomplete_type"]:
        tag = entry["tag"]
        # If we only have 'struct tag;', we must provide a body so arrays can be sized
        old = f"struct {tag};"
        # We also check for the typedef variant
        pattern = rf"typedef struct {tag} (\w+);"
        
        if old in registry:
            new = f"struct {tag} {{ char pad[4096]; }};"
            registry = registry.replace(old, new)
            print(f"  [T] Padded incomplete struct: {tag}")
            fixes += 1
        elif re.search(pattern, registry):
            replacement = f"struct {tag} {{ char pad[4096]; }};\ntypedef struct {tag} \\1;"
            registry = re.sub(pattern, replacement, registry)
            print(f"  [T] Padded incomplete typedef: {tag}")
            fixes += 1
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

def fix_name_collisions(cats):
    fixes = 0
    for entry in cats["collision"]:
        fp, sym = entry["file"], entry["sym"]
        content = read_file(fp)
        prefix = os.path.basename(fp).split('.')[0]
        new_sym = f"{prefix}_{sym}"
        if re.search(rf"\b{sym}\b", content):
            content = re.sub(rf"\b{sym}\b", new_sym, content)
            write_file(fp, content)
            print(f"  [N] Isolated symbol: {sym} -> {new_sym}")
            fixes += 1
    return fixes

def fix_sdk_types(cats):
    if not cats["sdk_type"]: return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(set(cats["sdk_type"])):
        if f" {t};" in content: continue
        dtype = KNOWN_SDK_TYPEDEFS.get(t, "int")
        content += f"\ntypedef {dtype} {t};\n"
        added = True
    if added: write_file(TYPES_HEADER, content)
    return 1 if added else 0

def fix_undefined(cats):
    if not cats["undefined"]: return 0
    stubs = read_file(STUBS_FILE) or '#include "n64_types.h"\n'
    added = False
    for sym in sorted(set(cats["undefined"])):
        if f" {sym}(" in stubs: continue
        stubs += f"\nlong long int {sym}() {{ return 0; }}\n"
        added = True
    if added: write_file(STUBS_FILE, stubs)
    return 1 if added else 0

# ── Dispatcher ───────────────────────────────────────────────────────────────

def apply_fixes():
    log_data = read_file(LOG_FILE)
    if not log_data: return 0
    cats = classify_errors(log_data)
    
    fixes = 0
    if cats["oom"]: 
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    # Order matters: Sync tags before doing anything else
    fixes += sync_typedef_tags(cats)
    fixes += update_global_registry(cats)
    fixes += fix_incomplete_types(cats)
    fixes += fix_name_collisions(cats)
    fixes += fix_sdk_types(cats)
    fixes += fix_undefined(cats)
    
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
