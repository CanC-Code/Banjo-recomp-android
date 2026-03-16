import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"

def run_build():
    print("\n🚀 Starting Build Cycle...")
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
    # Updated to catch .c, .cpp, and .h files
    file_regex = r"(/[^\s:]+\.(?:c|cpp|h|hpp))"
    
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    null_errs = re.findall(file_regex + r":(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'", log_data)

    # Types that belong in n64_types.h
    CORE_TYPES = {"OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "OSContPad", "Vtx", "Mtx", "ALHeap"}

    for filepath, t_name in set(type_errs):
        if os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            
            if t_name in CORE_TYPES:
                # Force include our master header
                if 'include "ultra/n64_types.h"' not in content:
                    with open(filepath, "w") as f: f.write('#include "ultra/n64_types.h"\n' + content)
                    print(f"  [+] Injected n64_types.h into {os.path.basename(filepath)} (Fixes {t_name})")
                    fixes += 1
            else:
                # Standard struct injection
                decl = f"typedef struct {t_name} {t_name};\n"
                if decl not in content:
                    with open(filepath, "w") as f: f.write(decl + content)
                    print(f"  [+] Injected type: {t_name} in {os.path.basename(filepath)}")
                    fixes += 1

    for filepath, var_name in set(id_errs):
        if var_name.startswith(("D_", "sCh")) and os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            decl = f"extern u8 {var_name}[];\n"
            if decl not in content:
                with open(filepath, "w") as f: f.write(decl + content)
                print(f"  [+] Injected extern: {var_name}")
                fixes += 1

    for filepath, line_str in set(null_errs):
        idx = int(line_str) - 1
        if os.path.exists(filepath):
            with open(filepath, "r") as f: lines = f.readlines()
            if idx < len(lines) and "NULL" in lines[idx]:
                lines[idx] = lines[idx].replace("NULL", "0")
                with open(filepath, "w") as f: f.writelines(lines)
                print(f"  [+] Fixed NULL float on line {line_str}")
                fixes += 1
                
    if fixes == 0:
        print("\n⚠️ Searching for new unhandled compiler errors...")
        unhandled = re.findall(r"error: (.*)", log_data)
        if unhandled:
            print("\n🚨 NEW ERRORS:")
            for err in list(dict.fromkeys(unhandled))[:5]: print(f"  - {err}")
    return fixes

def main():
    for i in range(1, 16):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        if apply_fixes() == 0:
            print("\n🛑 Stopping loop. No fixable patterns found.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
