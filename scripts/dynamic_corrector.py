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
    # Improved regex to handle relative and absolute paths
    file_regex = r"(\S+\.(?:c|cpp|h|hpp))"
    
    # Error Patterns
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    null_errs = re.findall(file_regex + r":(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'", log_data)

    # Mappings for System/POSIX identifiers with mandatory macros
    ID_TO_HEADER = {
        "sched_yield": "#define _GNU_SOURCE\n#include <sched.h>\n",
        "M_PI": "#define _USE_MATH_DEFINES\n#include <math.h>\n",
        "timespec": "#define _POSIX_C_SOURCE 199309L\n#include <time.h>\n",
        "uintptr_t": "#include <stdint.h>\n",
        "size_t": "#include <stddef.h>\n",
        "memcpy": "#include <string.h>\n"
    }

    # Core N64 types
    CORE_N64_TYPES = {"OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "OSContPad", "Vtx", "Mtx", "ALHeap"}

    # 1. Fix Unknown Types
    for filepath, t_name in set(type_errs):
        if os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            if t_name in ID_TO_HEADER:
                header = ID_TO_HEADER[t_name]
                if header not in content:
                    with open(filepath, "w") as f: f.write(header + content)
                    print(f"  [+] Injected {header.strip()} for type {t_name}")
                    fixes += 1
            elif t_name in CORE_N64_TYPES:
                if 'include "ultra/n64_types.h"' not in content:
                    with open(filepath, "w") as f: f.write('#include "ultra/n64_types.h"\n' + content)
                    print(f"  [+] Injected n64_types.h into {os.path.basename(filepath)}")
                    fixes += 1
            else:
                decl = f"typedef struct {t_name} {t_name};\n"
                if decl not in content:
                    with open(filepath, "w") as f: f.write(decl + content)
                    print(f"  [+] Injected struct typedef: {t_name}")
                    fixes += 1

    # 2. Fix Undeclared Identifiers
    for filepath, var_name in set(id_errs):
        if os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            if var_name in ID_TO_HEADER:
                header = ID_TO_HEADER[var_name]
                if header not in content:
                    with open(filepath, "w") as f: f.write(header + content)
                    print(f"  [+] Injected {header.strip()} for identifier {var_name}")
                    fixes += 1
            elif var_name.startswith(("D_", "sCh")):
                decl = f"extern u8 {var_name}[];\n"
                if decl not in content:
                    with open(filepath, "w") as f: f.write(decl + content)
                    print(f"  [+] Injected extern: {var_name}")
                    fixes += 1

    # 3. Fix NULL-to-Float
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
            print("\n🚨 NEW ERRORS DETECTED:")
            for err in list(dict.fromkeys(unhandled))[:5]: print(f"  - {err}")
                
    return fixes

def main():
    for i in range(1, 16):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        applied_fixes = apply_fixes()
        if applied_fixes == 0:
            print("\n🛑 Loop halted. No fixable patterns found.")
            break
        print(f"🛠️ Applied {applied_fixes} fixes. Restarting...")
        time.sleep(1)

if __name__ == "__main__":
    main()
