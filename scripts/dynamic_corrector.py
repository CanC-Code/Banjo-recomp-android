import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"

def run_build():
    print("\n🚀 Starting build cycle...")
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir): os.makedirs(log_dir)

    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(GRADLE_CMD, stdout=log, stderr=subprocess.STDOUT, text=True)
        process.wait()
    return process.returncode == 0

def apply_fixes():
    if not os.path.exists(LOG_FILE): return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f: log_data = f.read()

    fixes = 0
    # Fix 1: Unknown Types
    type_errs = re.findall(r"(/[^\s:]+\.c):\d+:\d+: error: unknown type name '([^']+)'", log_data)
    # Fix 2: NULL-to-Float (Line specific)
    null_errs = re.findall(r"(/[^\s:]+\.c):(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'", log_data)

    for filepath, t_name in set(type_errs):
        if os.path.exists(filepath):
            with open(filepath, "r") as f: lines = f.readlines()
            decl = f"typedef struct {t_name} {t_name};\n"
            if decl not in lines:
                lines.insert(0, decl)
                with open(filepath, "w") as f: f.writelines(lines)
                print(f"  [+] Added type: {t_name} in {os.path.basename(filepath)}")
                fixes += 1

    for filepath, line_str in null_errs:
        idx = int(line_str) - 1
        if os.path.exists(filepath):
            with open(filepath, "r") as f: lines = f.readlines()
            if idx < len(lines) and "NULL" in lines[idx]:
                lines[idx] = lines[idx].replace("NULL", "0")
                with open(filepath, "w") as f: f.writelines(lines)
                print(f"  [+] Fixed NULL-float on line {line_str}")
                fixes += 1
    return fixes

def main():
    for i in range(1, 16):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ SUCCESS!")
            return
        if apply_fixes() == 0:
            print("\n🛑 No more fixable errors.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
