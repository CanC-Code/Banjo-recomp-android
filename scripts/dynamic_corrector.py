import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"

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
    # Robust regex for paths
    file_regex = r"(/[^:\s]+):"
    
    affected_files = set()
    for line in log_data.split('\n'):
        if "error:" in line:
            match = re.search(file_regex, line.strip())
            if match:
                path = match.group(1)
                # Only fix files that exist in our project space
                if os.path.exists(path) and "ndk" not in path and "/usr/include" not in path:
                    affected_files.add(path)

    for filepath in affected_files:
        try:
            with open(filepath, "r") as f: content = f.read()
        except: continue
        
        original_content = content

        # FIX: Priority Injection (Ensures n64_types.h is ALWAYS the first line)
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
