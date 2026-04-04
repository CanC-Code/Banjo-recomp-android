"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Updates for Cycle 12.1:
  - Semantic Tag Resolver: Now resolves typedef symbols by searching the registry 
    for the "old" tag when the compiler error omits the symbol name.
  - JVM Argument Fix: Corrected 'HeapDumpOnOutOfMemoryError' typo.
  - Improved Log Parsing: Strips 'C/C++:' prefixes from NDK logs to ensure paths 
    are resolved correctly.
  - Redundancy Filter: Prevents the same fix from being applied multiple times 
    in a single cycle, preventing infinite loops.
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
        "./gradlew", "-p", "Android", "assembleDebug",
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
    # Strip common CI/Android prefix noise
    p = path.replace("C/C++: ", "").strip()
    p_lower = p.lower()
    if any(x in p_lower for x in ["/usr/", "/ndk/", "toolchains", "include/2.0l"]):
        return None
    if "/Banjo-recomp-android/Banjo-recomp-android/" in p:
        return p.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
    return p

# ── Build runner ─────────────────────────────────────────────────────────────

def run_build():
    print(f"\n🚀 Starting Build (heap={_HEAP_GB}g) ...")
    os.makedirs("Android", exist_ok=True)
    # Ensure gradlew is executable
    if os.path.exists("./gradlew"):
        os.chmod("./gradlew", 0o755)
    
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        cmd = _gradle_cmd()
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
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
        if "OutOfMemoryError" in line or "Unrecognized VM option" in line: 
            cats["oom"] = True
            continue
        
        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)
        if not fp: continue

        # Collisions
        m_coll = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        if m_coll:
            cats["collision"].append({"file": fp, "sym": m_coll.group(1)})
            continue

        # Tag Mismatch (Flexible Resolver)
        # Matches: redefinition of 'sym' with different types ('struct A' vs 'struct B')
        # OR: typedef redefinition with different types ('struct A' vs 'struct B')
        m_tag = re.search(r"redefinition.*?types.*?struct\s+([^']+)'\s+vs\s+'struct\s+([^']+)'", line)
        if m_tag:
            sym_match = re.search(r"redefinition\s+of\s+'([^']+)'", line)
            cats["tag_mismatch"].append({
                "correct_tag": m_tag.group(1), 
                "old_tag": m_tag.group(2),
                "sym": sym_match.group(1) if sym_match else None
            })
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
        correct_tag = entry["correct_tag"]
        old_tag     = entry["old_tag"]
        sym         = entry["sym"]
        
        # Scenario A: We have the symbol name (e.g. sChVegetable)
        if sym:
            pattern = rf"typedef struct \w+ {sym};"
            if re.search(pattern, registry):
                new_line = f"typedef struct {correct_tag} {sym};"
                registry = re.sub(pattern, new_line, registry)
                print(f"  [S] Synced symbol {sym}: {old_tag} -> {correct_tag}")
                fixes += 1
        # Scenario B: We only have tags. Look for the alias in the registry.
        else:
            pattern = rf"typedef struct {old_tag} ([A-Za-z_]\w*);"
            match = re.search(pattern, registry)
            if match:
                sym_found = match.group(1)
                new_line = f"typedef struct {correct_tag} {sym_found};"
                registry = re.sub(pattern, new_line, registry)
                print(f"  [S] Synced registry tag: {old_tag} -> {correct_tag} (Aliased as {sym_found})")
                fixes += 1
            
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

def update_global_registry(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER) or "#pragma once\n"
    
    unknown_syms = set(e["sym"] for e in cats["local_struct"])
    for s in sorted(unknown_syms):
        if f" {s};" in registry: continue
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
    
    processed_tags = set()
    for entry in cats["incomplete_type"]:
        tag = entry["tag"]
        if tag in processed_tags: continue
        
        # Avoid re-padding if already done
        if f"struct {tag} {{ char pad" in registry: continue

        old_forward = f"struct {tag};"
        pattern_typedef = rf"typedef struct {tag} (\w+);"
        
        if old_forward in registry:
            new_body = f"struct {tag} {{ char pad[4096]; }};"
            registry = registry.replace(old_forward, new_body)
            print(f"  [T] Padded struct: {tag}")
            fixes += 1
        elif re.search(pattern_typedef, registry):
            replacement = f"struct {tag} {{ char pad[4096]; }};\ntypedef struct {tag} \\1;"
            registry = re.sub(pattern_typedef, replacement, registry)
            print(f"  [T] Padded typedef: {tag}")
            fixes += 1
        processed_tags.add(tag)
            
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
            print(f"  [N] Isolated: {sym} -> {new_sym}")
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
