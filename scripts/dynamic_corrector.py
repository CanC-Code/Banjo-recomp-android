"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.

Cycle 15 Updates:
  - Redefinition Guard: Refined 'fix_incomplete_types' to use a strict membership 
    check before adding struct bodies, preventing the LetterFloorTile loop.
  - POSIX Collision Isolation: Automatically renames common conflicting symbols 
    (close, read, open, write) to file-prefixed versions (e.g., lockup_close).
  - Registry Pruning: Automatically removes redundant forward declarations when 
    a full padded body is present in n64_autodecls.h.
  - Path Normalization: Strips 'C/C++:' and absolute prefixing for cleaner logs.
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
    root = os.getcwd()
    candidates = [
        os.path.join(root, "Android", "gradlew"),
        os.path.join(root, "gradlew"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                os.chmod(p, 0o755)
                return os.path.abspath(p)
            except Exception: pass
    return "gradle"

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
    "OSTime":        "unsigned long long",
    "OSMesg":        "unsigned long long",
    "n64_bool":      "int",
    "u8": "unsigned char", "u16": "unsigned short", "u32": "unsigned int", "u64": "unsigned long long",
    "s8": "signed char",   "s16": "short",          "s32": "int",          "s64": "long long",
    "f32": "float",        "f64": "double",
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
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@~])', '', line)
                log.write(clean); print(clean, end="")
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}"); return False

# ── Error classifier ──────────────────────────────────────────────────────────

def classify_errors(log_data):
    cats = {
        "tag_mismatch":    [],
        "incomplete_type": [],
        "local_struct":    [],
        "collision":       [],
        "undefined":       [],
        "sdk_type":        [],
        "oom":             False,
    }

    lines = log_data.splitlines()
    for i, line in enumerate(lines):
        if "OutOfMemoryError" in line: cats["oom"] = True; continue
        
        # Tag Mismatch Resolver
        m_tag = re.search(r"redefinition.*?struct\s+([^']+)'\s+vs\s+'struct\s+([^']+)'", line)
        if m_tag:
            correct, old = m_tag.group(1), m_tag.group(2)
            sym = None
            for offset in [0, -1]:
                if i + offset < 0: continue
                s_match = re.search(r"redefinition\s+of\s+'([^']+)'", lines[i+offset])
                if s_match: sym = s_match.group(1); break
            cats["tag_mismatch"].append({"correct_tag": correct, "old_tag": old, "sym": sym})
            continue

        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)
        if not fp: continue

        # Namespace Collisions (e.g., 'close' in lockup.c)
        m_coll = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        if m_coll:
            cats["collision"].append({"file": fp, "sym": m_coll.group(1)})
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

        m_def = re.search(r"(?:undefined symbol:|undefined reference to `)([^']+)'?", line)
        if m_def: cats["undefined"].append(m_def.group(1).strip("`' "))

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def fix_name_collisions(cats):
    fixes = 0
    for entry in cats["collision"]:
        fp, sym = entry["file"], entry["sym"]
        content = read_file(fp)
        if not content: continue
        
        prefix = os.path.basename(fp).split('.')[0]
        new_sym = f"{prefix}_{sym}"
        
        if re.search(rf"\b{sym}\b", content):
            content = re.sub(rf"\b{sym}\b", new_sym, content)
            write_file(fp, content)
            print(f"  [N] Isolated Symbol: {fp} ({sym} -> {new_sym})")
            fixes += 1
    return fixes

def sync_typedef_tags(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    for entry in cats["tag_mismatch"]:
        correct, old, sym = entry["correct_tag"], entry["old_tag"], entry["sym"]
        if not sym:
            lookup = re.search(rf"typedef struct {old} ([A-Za-z_]\w*);", registry)
            if lookup: sym = lookup.group(1)
        if sym:
            pattern = rf"typedef struct \w+ {sym};"
            if re.search(pattern, registry):
                registry = re.sub(pattern, f"typedef struct {correct} {sym};", registry)
                print(f"  [S] Synced Tag: {sym} -> {correct}"); fixes += 1
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

def update_global_registry(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER) or "#pragma once\n"
    unknown_syms = set(e["sym"] for e in cats["local_struct"])
    for s in sorted(unknown_syms):
        if f" {s};" in registry: continue
        registry += f"typedef struct {s}_s {s};\n"
        print(f"  [R] Registry Added: {s}"); fixes += 1
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
        # Skip if a padded body already exists to prevent redefinition loops
        if f"struct {tag} {{ char pad" in registry:
            continue
            
        # Promote forward declaration to padded body
        if f"struct {tag};" in registry:
            registry = registry.replace(f"struct {tag};", f"struct {tag} {{ char pad[4096]; }};")
            print(f"  [T] Promoted Struct: {tag}"); fixes += 1
        elif rf"typedef struct {tag} " in registry:
            registry = re.sub(rf"typedef struct {tag} (\w+);", f"struct {tag} {{ char pad[4096]; }};\ntypedef struct {tag} \\1;", registry)
            print(f"  [T] Promoted Typedef: {tag}"); fixes += 1
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

# ── Dispatcher ───────────────────────────────────────────────────────────────

def apply_fixes():
    log_data = read_file(LOG_FILE)
    if not log_data: return 0
    cats = classify_errors(log_data)
    fixes = 0
    if cats["oom"]: global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    fixes += sync_typedef_tags(cats)
    fixes += fix_name_collisions(cats)
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
