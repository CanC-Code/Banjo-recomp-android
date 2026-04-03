import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
SDK_INCLUDE_DIR = "include"

def strip_ansi(text):
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
    file_regex = r"(\S+\.[ch](?:pp)?)"
    CORE_N64 = {"__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer", "Actor", "ActorMarker", "OSContPad"}

    error_lines = [line for line in log_data.split('\n') if "error:" in line]
    affected_files = set()
    for line in error_lines:
        match = re.search(file_regex, line)
        if match: affected_files.add(match.group(1))

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # FIX A: The 'close' Conflict
        if "declaration of 'close' follows non-static" in log_data or "lockup.c" in filepath:
            if "bka_close" not in content:
                content = re.sub(r'\bclose\b', 'bka_close', content)
                print(f"  [-] Renamed internal 'close' -> 'bka_close' in {os.path.basename(filepath)}")
                fixes += 1

        # FIX B: Intelligent Purifier (Purge empty declarations, keep bodies)
        for symbol in CORE_N64:
            pattern = rf"^(?:extern|volatile|static|typedef)?\s+[^;{{}}]+\s+{re.escape(symbol)}\b[^;{{}}]*;"
            match = re.search(pattern, content, re.MULTILINE)
            if match and '{' not in match.group(0):
                content = re.sub(pattern, f"/* Authority Strategy Purge: {symbol} */", content, flags=re.MULTILINE)
                print(f"  [🪠] Purged local redeclaration of {symbol}")
                fixes += 1

        # FIX C: 'actor' pointer correction
        if "use of undeclared identifier 'actor'" in log_data and "this" in content:
            if "Actor *actor =" not in content:
                content = re.sub(r'(\{)', r'\1\n    Actor *actor = (Actor *)this;', content, count=1)
                print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
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
