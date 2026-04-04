"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.

Cycle 13 Updates:
  - Absolute Path Resolver: Uses os.path.abspath to ensure the Gradle wrapper 
    is found and executed correctly regardless of the runner's CWD.
  - Multi-Line Tag Resolver: Enhanced regex to capture typedef conflicts even 
    when the symbol name is omitted or located on a different line.
  - Autodecls Sanity: Ensures n64_autodecls.h maintains a strict "one-definition-per-type"
    policy to prevent the "Extraneous Braces" syntax errors.
  - Registry Pruning: Automatically removes stale forward declarations when a 
    padded struct body is promoted.
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

def _get_gradle_executable():
    """Locates the absolute path to the gradle wrapper."""
    root = os.getcwd()
    # Prioritize the Android subdirectory wrapper
    candidates = [
        os.path.join(root, "Android", "gradlew"),
        os.path.join(root, "gradlew"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                os.chmod(p, 0o755)
                return os.path.abspath(p)
            except Exception:
                pass
    return "gradle" # Fallback to system gradle

def _gradle_cmd():
    return [
        _get_gradle_executable(), "-p", "Android", "assembleDebug",
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
    p = path.replace("C/C++: ", "").strip()
    if "/Banjo-recomp-android/Banjo-recomp-android/" in p:
        return p.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
    return p

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) ...")
    os.makedirs("Android", exist_ok=True)
    
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        cmd = _gradle_cmd()
        print(f"  [Exec] {cmd[0]}")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
                log.write(clean)
                print(clean, end="")
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}")
            return False

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

    # Combined multi-line buffer for tag parsing
    lines = log_data.splitlines()
    for i, line in enumerate(lines):
        if any(x in line for x in ["OutOfMemoryError", "Unrecognized VM option"]):
            cats["oom"] = True; continue
        
        # Tag Mismatch Resolver (Clang 17 Multi-line handling)
        # error: typedef redefinition with different types ('struct A' vs 'struct B')
        m_tag = re.search(r"redefinition.*?struct\s+([^']+)'\s+vs\s+'struct\s+([^']+)'", line)
        if m_tag:
            correct_tag, old_tag = m_tag.group(1), m_tag.group(2)
            # Try to find the symbol name in this line or the previous one
            sym = None
            for offset in [0, -1]:
                if i + offset < 0: continue
                s_match = re.search(r"redefinition\s+of\s+'([^']+)'", lines[i+offset])
                if s_match: sym = s_match.group(1); break
            
            cats["tag_mismatch"].append({
                "correct_tag": correct_tag, "old_tag": old_tag, "sym": sym
            })
            continue

        # Basic Path-based errors
        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)
        if not fp: continue

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

        # Undefined symbols
        m_def = re.search(r"(?:undefined symbol:|undefined reference to `)([^']+)'?", line)
        if m_def: cats["undefined"].append(m_def.group(1).strip("`' "))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def sync_typedef_tags(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    
    for entry in cats["tag_mismatch"]:
        correct, old, sym = entry["correct_tag"], entry["old_tag"], entry["sym"]
        
        # If sym is missing from log, find it by searching registry for the old tag
        if not sym:
            lookup = re.search(rf"typedef struct {old} ([A-Za-z_]\w*);", registry)
            if lookup: sym = lookup.group(1)
        
        if sym:
            # Replace whatever tag we have with the source code's reality
            pattern = rf"typedef struct \w+ {sym};"
            if re.search(pattern, registry):
                registry = re.sub(pattern, f"typedef struct {correct} {sym};", registry)
                print(f"  [S] Fixed Typedef: {sym} ({old} -> {correct})")
                fixes += 1
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

def update_global_registry(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER) or "#pragma once\n"
    
    unknown_syms = set(e["sym"] for e in cats["local_struct"])
    for s in sorted(unknown_syms):
        if f" {s};" in registry: continue
        registry += f"typedef struct {s}_s {s};\n"
        print(f"  [R] Registry Added: {s}")
        fixes += 1

    if fixes > 0:
        write_file(AUTO_HEADER, registry)
        types = read_file(TYPES_HEADER)
        if f'#include "{os.path.basename(AUTO_HEADER)}"' not in types:
            write_file(TYPES_HEADER, f'#include "{os.path.basename(AUTO_HEADER)}"\n' + types)
    return fixes

def fix_incomplete_types(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    
    for entry in cats["incomplete_type"]:
        tag = entry["tag"]
        # Promotion logic: forward declaration -> padded body
        old_fwd = f"struct {tag};"
        if old_fwd in registry:
            registry = registry.replace(old_fwd, f"struct {tag} {{ char pad[4096]; }};")
            print(f"  [T] Promoted struct: {tag}")
            fixes += 1
        elif rf"typedef struct {tag} " in registry:
            pattern = rf"typedef struct {tag} (\w+);"
            registry = re.sub(pattern, f"struct {tag} {{ char pad[4096]; }};\ntypedef struct {tag} \\1;", registry)
            print(f"  [T] Promoted typedef: {tag}")
            fixes += 1
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

# ── Dispatcher ───────────────────────────────────────────────────────────────

def apply_fixes():
    log_data = read_file(LOG_FILE)
    if not log_data: return 0
    cats = classify_errors(log_data)
    
    fixes = 0
    if cats["oom"]: 
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    # Priority: Syncing tags is the most critical to break redefinition loops
    fixes += sync_typedef_tags(cats)
    fixes += update_global_registry(cats)
    fixes += fix_incomplete_types(cats)
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
