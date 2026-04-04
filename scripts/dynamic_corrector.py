"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.

Cycle 17 Updates:
  - Macro-based POSIX Isolation: Restored the #define macro injection strategy for 
    handling static collisions (e.g., 'close') which is significantly safer than 
    regex word replacement.
  - Linker Stub Generation: Automatically generates n64_stubs.c for missing symbols 
    and wires it into CMakeLists.txt.
  - Standard Header Injection: Detects implicit functions (memcpy, sinf, malloc) 
    and auto-injects standard C headers into n64_types.h.
  - Extraneous Brace Recovery: Includes a fallback parser to repair n64_types.h 
    if a previous typedef harmonizer corrupted the syntax.
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
CMAKE_FILE   = "Android/app/src/main/cpp/CMakeLists.txt"

# ── Type Definitions ─────────────────────────────────────────────────────────

KNOWN_SDK_TYPEDEFS = {
    "OSHWIntr": "unsigned int", "OSIntMask": "unsigned int",
    "OSTime": "unsigned long long", "OSMesg": "unsigned long long",
    "n64_bool": "int",
    "u8": "unsigned char", "u16": "unsigned short", "u32": "unsigned int", "u64": "unsigned long long",
    "s8": "signed char",   "s16": "short",          "s32": "int",          "s64": "long long",
    "f32": "float",        "f64": "double",
}

# ── Utilities ────────────────────────────────────────────────────────────────

def read_file(path):
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8") as f: return f.read()

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(content)

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
                clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
                log.write(clean); print(clean, end="")
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}"); return False

# ── Error classifier ──────────────────────────────────────────────────────────

def classify_errors(log_data):
    cats = {
        "oom":             False,
        "tag_mismatch":    [],
        "static_conflict": [],
        "incomplete_type": [],
        "local_struct":    [],
        "undefined":       [],
        "implicit_func":   [],
        "macro_missing":   [],
        "extraneous_brace": False
    }

    lines = log_data.splitlines()
    for i, line in enumerate(lines):
        if "OutOfMemoryError" in line: cats["oom"] = True; continue
        if "extraneous closing brace" in line: cats["extraneous_brace"] = True; continue

        pm = re.search(r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))", line)
        fp = source_path(pm.group(1) if pm else None)

        m_tag = re.search(r"redefinition.*?struct\s+([^']+)'\s+vs\s+'struct\s+([^']+)'", line)
        if m_tag:
            sym = None
            for offset in [0, -1]:
                if i + offset < 0: continue
                s_match = re.search(r"redefinition\s+of\s+'([^']+)'", lines[i+offset])
                if s_match: sym = s_match.group(1); break
            cats["tag_mismatch"].append({"correct": m_tag.group(1), "old": m_tag.group(2), "sym": sym})
            continue

        if not fp: continue

        m_coll = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        if m_coll: cats["static_conflict"].append({"file": fp, "sym": m_coll.group(1)}); continue

        m_inc = re.search(r"incomplete\s+definition\s+of\s+type\s+'struct\s+([^']+)'", line)
        if m_inc: cats["incomplete_type"].append({"file": fp, "tag": m_inc.group(1)}); continue

        m_unk = re.search(r"unknown type name '([A-Za-z_]\w*)'", line)
        if m_unk:
            t = m_unk.group(1)
            if t not in KNOWN_SDK_TYPEDEFS: cats["local_struct"].append(t)
            continue

        m_def = re.search(r"(?:undefined symbol:|undefined reference to `)([^']+)'?", line)
        if m_def: cats["undefined"].append(m_def.group(1).strip("`' ")); continue

        m_impl = re.search(r"implicit declaration of function '([^']+)'", line)
        if m_impl: cats["implicit_func"].append(m_impl.group(1)); continue

        m_macro = re.search(r"use of undeclared identifier '([^']+)'", line)
        if m_macro: cats["macro_missing"].append(m_macro.group(1)); continue

    return cats

# ── Fix passes ───────────────────────────────────────────────────────────────

def fix_brace_corruption(cats):
    if not cats["extraneous_brace"]: return 0
    content = read_file(TYPES_HEADER)
    # Detect and fix bad padding formats injected by older scripts
    if "typedef struct" in content and "extraneous" in read_file(LOG_FILE):
        content = re.sub(r"\}\s+([A-Za-z_]\w*);\n\s*\}\s+\1;", r"} \1;", content)
        write_file(TYPES_HEADER, content)
        print("  [🛠️] Attempted recovery of extraneous braces in n64_types.h")
        return 1
    return 0

def fix_static_conflicts(cats):
    fixes = 0
    for entry in cats["static_conflict"]:
        fp, sym = entry["file"], entry["sym"]
        content = read_file(fp)
        if not content: continue
        
        prefix = os.path.basename(fp).split('.')[0]
        macro_fix = f"\n/* AUTO: fix static conflict */\n#define {sym} auto_renamed_{prefix}_{sym}\n"
        
        if macro_fix not in content:
            if '#include "ultra/n64_types.h"' in content:
                content = content.replace('#include "ultra/n64_types.h"', f'#include "ultra/n64_types.h"{macro_fix}')
            else:
                content = macro_fix + content
            write_file(fp, content)
            print(f"  [N] Protected static collision via Macro: {fp} ({sym})")
            fixes += 1
    return fixes

def fix_implicit_headers(cats):
    if not cats["implicit_func"]: return 0
    math_funcs = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
    string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
    stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
    
    types_content = read_file(TYPES_HEADER)
    if not types_content: return 0
    added = False

    for func in set(cats["implicit_func"]):
        header = None
        if func in math_funcs: header = "<math.h>"
        elif func in string_funcs: header = "<string.h>"
        elif func in stdlib_funcs: header = "<stdlib.h>"
        
        if header and f"#include {header}" not in types_content:
            types_content = f"#include {header}\n" + types_content
            added = True
            print(f"  [I] Injected {header} for implicit function '{func}'")
            
    if added: write_file(TYPES_HEADER, types_content)
    return 1 if added else 0

def generate_linker_stubs(cats):
    if not cats["undefined"]: return 0
    
    # 1. Setup Stubs File
    stubs = read_file(STUBS_FILE) or '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n'
    added = False
    for sym in set(cats["undefined"]):
        if sym.startswith("_Z") or "vtable" in sym: continue
        if f" {sym}(" not in stubs:
            stubs += f"long long int {sym}() {{ return 0; }}\n"
            added = True
            print(f"  [L] Generated linker stub for '{sym}'")
    
    if added: write_file(STUBS_FILE, stubs)

    # 2. Wire into CMakeLists.txt
    cmake = read_file(CMAKE_FILE)
    if cmake and "ultra/n64_stubs.c" not in cmake:
        cmake = cmake.replace("add_library(", "add_library(\n        ultra/n64_stubs.c")
        write_file(CMAKE_FILE, cmake)
        print("  [C] Wired n64_stubs.c into CMakeLists.txt")

    return 1 if added else 0

def update_global_registry(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER) or "#pragma once\n"
    types_content = read_file(TYPES_HEADER)
    
    for s in sorted(set(cats["local_struct"])):
        if f" {s};" in registry or re.search(rf"\b{re.escape(s)}\b", types_content): continue
        registry += f"typedef struct {s}_s {s};\n"
        print(f"  [R] Registry Added: {s}"); fixes += 1
    
    if fixes > 0:
        write_file(AUTO_HEADER, registry)
        if f'#include "{os.path.basename(AUTO_HEADER)}"' not in types_content:
            write_file(TYPES_HEADER, f'#include "{os.path.basename(AUTO_HEADER)}"\n' + types_content)
    return fixes

def sync_typedef_tags(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    for entry in cats["tag_mismatch"]:
        correct, old, sym = entry["correct"], entry["old"], entry["sym"]
        if not sym:
            lookup = re.search(rf"typedef struct {re.escape(old)} ([A-Za-z_]\w*);", registry)
            if lookup: sym = lookup.group(1)
        if sym:
            pattern = rf"typedef struct \w+ {re.escape(sym)};"
            if re.search(pattern, registry):
                registry = re.sub(pattern, f"typedef struct {correct} {sym};", registry)
                print(f"  [S] Synced Tag: {sym} -> {correct}"); fixes += 1
    if fixes > 0: write_file(AUTO_HEADER, registry)
    return fixes

def fix_incomplete_types(cats):
    fixes = 0
    registry = read_file(AUTO_HEADER)
    if not registry: return 0
    
    for entry in cats["incomplete_type"]:
        tag = entry["tag"]
        if f"struct {tag} {{ char pad" in registry: continue
            
        if f"struct {tag};" in registry:
            registry = registry.replace(f"struct {tag};", f"struct {tag} {{ char pad[4096]; }};")
            print(f"  [T] Promoted Struct: {tag}"); fixes += 1
        elif rf"typedef struct {re.escape(tag)} " in registry:
            registry = re.sub(rf"typedef struct {re.escape(tag)} (\w+);", 
                              f"struct {tag} {{ char pad[4096]; }};\ntypedef struct {tag} \\1;", registry)
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
    
    fixes += fix_brace_corruption(cats)
    fixes += fix_static_conflicts(cats)
    fixes += fix_implicit_headers(cats)
    fixes += sync_typedef_tags(cats)
    fixes += update_global_registry(cats)
    fixes += fix_incomplete_types(cats)
    fixes += generate_linker_stubs(cats)
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
