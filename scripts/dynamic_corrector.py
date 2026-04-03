import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

def strip_ansi(text):
    """Removes terminal color codes that make errors invisible to regex."""
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
    # Capture filenames more broadly to catch all paths
    file_regex = r"(\S+\.[ch](?:pp)?)"
    
    # 1. THE CORE ENFORCEMENT LIST
    # These symbols MUST only exist in n64_types.h
    CORE_N64 = {
        "__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer",
        "OSIntMask", "OSTime", "OSMesgQueue", "OSThread", "Actor", "sChVegetable"
    }

    # 2. MATCH ALL ERRORS (Redefinitions, Mismatches, Namespace Collisions)
    # We look for the word 'error:' regardless of surrounding color codes
    error_blocks = re.findall(file_regex + r":\d+:\d+: error: (.*)", log_data)
    
    affected_files = set([re.search(file_regex, line).group(1) for line in log_data.split('\n') if "error:" in line])

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # FIX A: The 'close' Namespace Collision (lockup.c, castle.c, etc)
        # We rename the game's internal 'close' to 'bka_close' to avoid POSIX conflicts
        if "declaration of 'close' follows non-static" in log_data or "lockup.c" in filepath:
            if "bka_close" not in content:
                content = re.sub(r'\bclose\b', 'bka_close', content)
                print(f"  [🔀] Renamed game-internal 'close' -> 'bka_close' in {os.path.basename(filepath)}")
                fixes += 1

        # FIX B: The 'Authority' Purifier
        # Comment out local source declarations of symbols managed by the master header
        for symbol in CORE_N64:
            pattern = rf"^(?:extern|volatile|static|typedef)?\s+[^;{{}}]+\s+{re.escape(symbol)}\b[^;{{}}]*;"
            if re.search(pattern, content, re.MULTILINE):
                content = re.sub(pattern, f"/* Purged by Authority Strategy: {symbol} */", content, flags=re.MULTILINE)
                print(f"  [🪠] Purged local '{symbol}' declaration in {os.path.basename(filepath)}")
                fixes += 1

        # FIX C: Missing Header Injection
        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            print(f"  [+] Injected n64_types.h into {os.path.basename(filepath)}")
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
            # If we halt, show the first unhandled error to the user
            unhandled = re.findall(r"error: (.*)", log_data)
            if unhandled:
                print(f"  [!] First unhandled error: {unhandled[0]}")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
