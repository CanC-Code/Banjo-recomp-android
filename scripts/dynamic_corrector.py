import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

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
    # Robust regex to capture full paths even without extensions
    file_regex = r"^((?:/[^:/]+)+):"
    
    CORE_N64 = {"__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer", "Actor", "ActorMarker", "OSContPad"}

    affected_files = set()
    for line in log_data.split('\n'):
        if "error:" in line:
            match = re.search(file_regex, line.strip())
            if match:
                filepath = match.group(1)
                # Ignore system/NDK headers for correction
                if os.path.exists(filepath) and "/usr/include" not in filepath and "ndk" not in filepath:
                    affected_files.add(filepath)

    for filepath in affected_files:
        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # FIX: The 'close' Conflict
        if "follows non-static declaration" in log_data or "lockup.c" in filepath:
            if "bka_close" not in content:
                content = re.sub(r'\bclose\b', 'bka_close', content)
                print(f"  [-] Renamed 'close' -> 'bka_close' in {os.path.basename(filepath)}")
                fixes += 1

        # FIX: Priority Injection
        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            fixes += 1

        # FIX: 'actor' pointer correction
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
