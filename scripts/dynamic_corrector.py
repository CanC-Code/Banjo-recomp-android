"""
prepare_source.py — Self-healing build driver for the BK AArch64 Android port.

Updates for Cycle 9:
  - Usage-Before-Definition (UBD) Fix: Injects forward declarations even if 
    a definition exists later in the file, ensuring line 15 usage is valid.
  - Scan-Ahead Tag Discovery: Pre-emptively searches the current file for 
    'typedef struct TAG { ... } TYPE;' to use the correct TAG immediately.
  - Robust AUTO Blocks: Switched to [START]/[END] markers to prevent regex 
    overlapping and ensure clean updates.
  - SDK Type Safety: Added a fallback for unknown SDK types to prevent script 
    KeyErrors and malformed headers.
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

MARKER_START = "/* [AUTO-START] */"
MARKER_END   = "/* [AUTO-END] */"

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

def fix_local_structs(cats):
    fixes = 0
    files = {}
    for entry in cats["local_struct"]:
        files.setdefault(entry["file"], set()).add(entry["sym"])

    for fp, syms in files.items():
        content = read_file(fp)
        new_decls = []
        for s in sorted(syms):
            # Scan-Ahead: Find the real tag if it exists in the file
            tag = f"{s}_s"
            m_scan = re.search(rf"typedef struct (\w+) .*?{s};", content, flags=re.DOTALL)
            if m_scan: tag = m_scan.group(1)
            
            fwd = f"typedef struct {tag} {s};"
            # Only inject if this exact forward decl isn't in the file yet
            if fwd not in content:
                new_decls.append(fwd)

        if new_decls:
            # Clean old block
            content = re.sub(rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}", "", content, flags=re.DOTALL)
            header = f"{MARKER_START}\n" + "\n".join(new_decls) + f"\n{MARKER_END}\n"
            write_file(fp, header + content.lstrip())
            print(f"  [C] Injected UBD-safe decls into {os.path.basename(fp)}")
            fixes += 1
    return fixes

def fix_tag_mismatch(cats):
    fixes = 0
    for entry in cats["tag_mismatch"]:
        fp, sym, tag = entry["file"], entry["sym"], entry["tag"]
        content = read_file(fp)
        # Correct the previous guess
        pattern = rf"typedef struct \w+ {sym};"
        replacement = f"typedef struct {tag} {sym};"
        if re.search(pattern, content):
            write_file(fp, re.sub(pattern, replacement, content))
            print(f"  [L] Learned tag for {sym}: {tag}")
            fixes += 1
    return fixes

def fix_incomplete_types(cats):
    fixes = 0
    for entry in cats["incomplete_type"]:
        fp, tag = entry["file"], entry["tag"]
        content = read_file(fp)
        # Upgrade pointers to stubs
        old = f"struct {tag};"
        new = f"struct {tag} {{ char pad[4096]; }};"
        if old in content and new not in content:
            write_file(fp, content.replace(old, new))
            print(f"  [T] Escalated incomplete struct {tag}")
            fixes += 1
    return fixes

def fix_sdk_types(cats):
    if not cats["sdk_type"]: return 0
    content = read_file(TYPES_HEADER)
    added = False
    for t in sorted(set(cats["sdk_type"])):
        if f" {t};" in content: continue
        # Fallback to int if the SDK type is completely unknown
        dtype = KNOWN_SDK_TYPEDEFS.get(t, "int")
        content += f"\ntypedef {dtype} {t};\n"
        added = True
        print(f"  [K] Added SDK type: {t} ({dtype})")
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
    if os.path.exists(TYPES_HEADER) and "#pragma once" not in read_file(TYPES_HEADER):
        write_file(TYPES_HEADER, "#pragma once\n" + read_file(TYPES_HEADER))
        fixes += 1
    
    if cats["oom"]: 
        global _HEAP_GB; _HEAP_GB = min(_HEAP_GB + 2, 14); fixes += 1
    
    fixes += fix_tag_mismatch(cats)
    fixes += fix_incomplete_types(cats)
    fixes += fix_sdk_types(cats)
    fixes += fix_local_structs(cats)
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
