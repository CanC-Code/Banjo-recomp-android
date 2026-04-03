import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
SDK_INCLUDE_DIR = "include" # Adjust if your SDK headers are elsewhere

def strip_ansi(text):
    """Removes terminal color codes (\x1b[...) that break regex."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def harvest_macro(macro_name):
    """Searches SDK headers for a missing macro definition."""
    if not os.path.exists(SDK_INCLUDE_DIR): return None
    for root, _, files in os.walk(SDK_INCLUDE_DIR):
        for file in files:
            if not file.endswith('.h'): continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except: continue
            for i, line in enumerate(lines):
                if re.match(rf'^[ \t]*#[ \t]*define[ \t]+{macro_name}\b', line):
                    # Capture multi-line macros (ending in \)
                    macro_block = line
                    curr = i
                    while macro_block.strip().endswith('\\') and curr + 1 < len(lines):
                        curr += 1
                        macro_block += lines[curr]
                    return macro_block.strip()
    return None

def inject_to_header(block, name, label="Auto-Fixed"):
    """Injects a definition into the master n64_types.h before the final #endif."""
    if not os.path.exists(TYPES_HEADER): return False
    with open(TYPES_HEADER, "r") as f: content = f.read()
    if f"define {name}" in content or f"typedef" in content and f" {name}" in content:
        return False
    pos = content.rfind('#endif')
    if pos != -1:
        new_content = content[:pos] + f"\n/* {label}: {name} */\n{block}\n\n" + content[pos:]
        with open(TYPES_HEADER, "w") as f: f.write(new_content)
        return True
    return False

def run_build():
    print("\n🚀 Starting Build Cycle...")
    if not os.path.exists("Android"): os.makedirs("Android")
    # We capture stdout to strip ANSI codes before writing to the log file
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
    
    # Symbols that are strictly managed in n64_types.h
    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "OSIntMask",
        "__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer",
        "Gfx", "Acmd", "Vtx", "Mtx", "Actor"
    }

    # Extract Error Information
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    # Redefinition errors often look like: redefinition of 'var' with a different type
    redef_errs = re.findall(file_regex + r":\d+:\d+: error: (?:redefinition of|static declaration of) '([^']+)'", log_data)

    affected_files = set([e[0] for e in re.findall(file_regex + r":\d+:\d+: error:", log_data)])

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # 1. PURIFIER: Comment out local declarations of symbols in CORE_N64
        for symbol in CORE_N64:
            # Matches local externs/definitions: "extern volatile u32 __OSGlobalIntMask;" etc.
            pattern = rf"^(?:extern|volatile|static|typedef)?\s+[^;{{}}]+\s+{re.escape(symbol)}\b[^;{{}}]*;"
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, f"/* Purified local redeclaration of {symbol} */", content, flags=re.MULTILINE)
                print(f"  [🪠] Purged local '{symbol}' in {os.path.basename(filepath)}")
                fixes += 1

        # 2. SANITIZER: Rename clashing internal functions
        if "static void close(" in content or "void close(" in content:
             content = content.replace("close(", "bka_close(")
             print(f"  [-] Renamed internal 'close' to 'bka_close' in {os.path.basename(filepath)}")
             fixes += 1

        # 3. HARVESTER: Look for missing Macros/Constants
        file_ids = [i[1] for i in id_errs if i[0] == filepath]
        for identifier in file_ids:
            if identifier.startswith(("G_", "OS_", "GU_", "RM_")):
                macro = harvest_macro(identifier)
                if macro:
                    if inject_to_header(macro, identifier, "Harvested"):
                        print(f"  [🤖] Harvested SDK Macro: {identifier}")
                        fixes += 1
                else:
                    # Polyfill if not found in SDK
                    if inject_to_header(f"#define {identifier} 0", identifier, "Polyfill"):
                        print(f"  [⚠️] Polyfilled missing token: {identifier}")
                        fixes += 1

        # 4. INJECTOR: Ensure master header is included
        if any(sym in content for sym in CORE_N64) or "n64_types.h" not in content:
            if 'include "ultra/n64_types.h"' not in content:
                content = '#include "ultra/n64_types.h"\n' + content
                print(f"  [+] Injected n64_types.h into {os.path.basename(filepath)}")
                fixes += 1

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    if fixes == 0:
        print("\n⚠️ Checking for unhandled errors...")
        unhandled = re.findall(r"error: (.*)", log_data)
        if unhandled:
            print("\n🚨 UNHANDLED ERRORS DETECTED:")
            for err in list(dict.fromkeys(unhandled))[:5]: print(f"  - {err}")
            
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
