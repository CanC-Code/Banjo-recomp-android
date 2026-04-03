import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

def strip_ansi(text):
    """Removes hidden terminal color codes that break regex matching."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def run_build():
    print("\n🚀 Starting Build Cycle...")
    if not os.path.exists("Android"): os.makedirs("Android")
    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            clean_line = strip_ansi(line)
            log.write(clean_line)
            print(clean_line, end="") 
        process.wait()
    return process.returncode == 0

def apply_fixes():
    if not os.path.exists(LOG_FILE): return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f: log_data = f.read()

    fixes = 0
    file_regex = r"(\S+\.(?:c|cpp|h|hpp))"
    
    # Symbols managed strictly in n64_types.h
    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "OSIntMask",
        "__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer",
        "Gfx", "Acmd", "Vtx", "Mtx", "Actor"
    }

    # Enhanced error capturing
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    close_errs = re.findall(file_regex + r":\d+:\d+: error: static declaration of 'close' follows non-static declaration", log_data)
    redef_errs = re.findall(file_regex + r":\d+:\d+: error: .*?redefinition.*?'(?:struct )?([a-zA-Z0-9_]+)'", log_data)

    affected_files = set([e[0] for e in re.findall(file_regex + r":\d+:\d+: error:", log_data)])

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # 1. PURIFIER: Force local source files to use the Header's version of core variables
        for symbol in CORE_N64:
            pattern = rf"^(?:extern|volatile|static|typedef)?\s+[^;{{}}]+\s+{re.escape(symbol)}\b[^;{{}}]*;"
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, f"/* Purged local redeclaration of {symbol} */", content, flags=re.MULTILINE)
                print(f"  [🪠] Purged local '{symbol}' in {os.path.basename(filepath)}")
                fixes += 1

        # 2. LOCKUP FIX: Rename game's 'close' function to avoid conflict with unistd.h
        if "close" in close_errs or any(f in filepath for f in ["lockup.c", "castle.c"]):
            if "bka_close" not in content:
                content = re.sub(r'\bclose\b', 'bka_close', content)
                print(f"  [-] Safely renamed internal 'close' to 'bka_close' in {os.path.basename(filepath)}")
                fixes += 1

        # 3. TYPE HARMONIZER: Resolve redefinitions by commenting out local versions
        for name in [r[1] for r in redef_errs if r[0] == filepath]:
            if name in CORE_N64:
                pattern_struct = rf"(typedef\s+(?:struct|union)\s*(?:[a-zA-Z0-9_]+\s*)?\{{.*?\}}\s*{name}\s*;)"
                content = re.sub(pattern_struct, r"/* \1 (Master Header Fix) */", content, flags=re.DOTALL)
                pattern_simple = rf"(typedef\s+[^;{{}}]+\s+{name}\s*;)"
                content = re.sub(pattern_simple, r"/* \1 (Master Header Fix) */", content)
                print(f"  [-] Resolved redefinition of {name} in {os.path.basename(filepath)}")
                fixes += 1

        # 4. INJECTOR: Ensure master header is present
        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            fixes += 1

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    return fixes

def main():
    for i in range(1, 100):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        if apply_fixes() == 0:
            print("\n🛑 Loop halted. No fixable patterns found.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
