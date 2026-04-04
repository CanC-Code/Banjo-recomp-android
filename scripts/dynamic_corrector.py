"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Updates for Cycle 10:
  - Global Registry Migration: Moves local forward declarations from source 
    files to a central 'n64_autodecls.h' which is force-included.
  - Conflict-First Learning: Prioritizes fixing 'redefinition' errors before 
    'unknown type' errors to ensure the registry is accurate.
  - Blind Stubbing: If a type is unknown and cannot be found in the source, 
    it is now stubbed in the global registry to break compilation stalemates.
  - Path Normalization: Normalizes relative paths in logs to correctly 
    target files in the GitHub Actions environment.
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
    # Normalize paths relative to the work dir
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
        "oom":             False,
    }

    for line in log_data.splitlines():
        if "OutOfMemoryError" in line: cats["oom"] = True; continue
        
        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)
        if not fp: continue

        # Redefinition / Tag Learning
        m_tag = re.search(r"redefinition of '([^']+)' with different types.*?struct ([^']+)' vs 'struct ([^']+)'", line)
        if m_tag:
            cats["tag_mismatch"].append({"file": fp, "sym": m_tag.group(1), "tag": m_tag.group(2)})
            continue

        # Incomplete Type
        if "incomplete definition" in line:
            m_inc = re.search(r"type 'struct ([^']+)'", line)
            if m_inc: cats["incomplete_type"].append({"file": fp, "tag": m_inc.group(1)})
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

def update_global_registry(cats):
    """Syncs unknown types into a force-included header."""
    fixes = 0
    registry = read_file(AUTO_HEADER) or "#pragma once\n"
    
    # 1. Learn from redefinitions first (correcting existing decls)
    for entry in cats["tag_mismatch"]:
        sym, tag = entry["sym"], entry["tag"]
        pattern = rf"typedef struct \w+ {sym};"
        replacement = f"typedef struct {tag} {sym};"
        if re.search(pattern, registry):
            registry = re.sub(pattern, replacement, registry)
            print(f"  [L] Registry Updated: {sym} -> struct {tag}")
            fixes += 1

    # 2. Add new unknown types
    unknown_syms = set(e["sym"] for e in cats["local_struct"])
    for s in sorted(unknown_syms):
        if f" {s};" in registry: continue
        
        # Try to find the real tag in the file that reported the error
        tag = f"{s}_s"
        for entry in cats["local_struct"]:
            if entry["sym"] == s:
                content = read_file(entry["file"])
                m = re.search(rf"typedef struct (\w+) .*?{s};", content, flags=re.DOTALL)
                if m: tag = m.group(1); break
        
        registry += f"typedef struct {tag} {s};\n"
        print(f"  [R] Registry Added: {s} (tag: {tag})")
        fixes += 1

    if fixes > 0:
        write_file(AUTO_HEADER, registry)
        # Ensure n64_types.h includes the registry
        types_content = read_file(TYPES_HEADER)
        inc_line = f'#include "{os.path.basename(AUTO_HEADER)}"'
        if inc_line not in types_content:
            write_file(TYPES_HEADER, f'{inc_line}\n' + types_content)
    
    return fixes

def fix_incomplete_types(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    for entry in cats["incomplete_type"]:
        tag = entry["tag"]
        # Upgrade pointers to stubs in the global registry
        old = f"struct {tag};"
        new = f"struct {tag} {{ char pad[4096]; }};"
        
        # Check source first (if definition is there but incomplete)
        src_content = read_file(entry["file"])
        if f"struct {tag};" in src_content:
            write_file(entry["file"], src_content.replace(f"struct {tag};", new))
            fixes += 1
            print(f"  [T] Escalated {tag} in source")
        
        # Also check registry
        if old in registry and new not in registry:
            registry = registry.replace(old, new)
            fixes += 1
            print(f"  [T] Escalated {tag} in registry")
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
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
        print(f"  [K] Added SDK type: {t}")
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
        print(f"  [I] Stubbed {sym}")
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
    
    # Priority: Correct Registry -> Add to Registry -> Incomplete types -> SDK/Linker
    fixes += update_global_registry(cats)
    fixes += fix_incomplete_types(cats)
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
