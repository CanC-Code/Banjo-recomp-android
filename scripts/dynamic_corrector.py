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
    file_regex = r"(\S+\.(?:c|cpp|h|hpp))"
    
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    linkage_errs = re.findall(file_regex + r":\d+:\d+: error: declaration of '([^']+)' has a different language linkage", log_data)

    SCALARS = {
        "u8": "typedef unsigned char u8;\n",
        "s8": "typedef signed char s8;\n",
        "u16": "typedef unsigned short u16;\n",
        "s16": "typedef short s16;\n",
        "u32": "typedef unsigned int u32;\n",
        "s32": "typedef int s32;\n"
    }

    CORE_N64 = {"OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "ALHeap", "ADPCM_STATE"}

    affected_files = set([e[0] for e in type_errs] + [e[0] for e in id_errs] + [e[0] for e in linkage_errs])

    for filepath in affected_files:
        if not os.path.exists(filepath): continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content
        
        file_errors = [t[1] for t in type_errs if t[0] == filepath] + [i[1] for i in id_errs if i[0] == filepath]
        
        for err in set(file_errors):
            if err in SCALARS:
                decl = SCALARS[err]
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected scalar polyfill: {err} in {os.path.basename(filepath)}")
                    fixes += 1
            elif err in CORE_N64:
                if 'include "ultra/n64_types.h"' not in content:
                    content = '#include "ultra/n64_types.h"\n' + content
                    print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
                    fixes += 1
            elif err.startswith(("D_", "sCh")):
                decl = f"extern u8 {err}[];\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected extern: {err}")
                    fixes += 1

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    return fixes

def main():
    for i in range(1, 30):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        if apply_fixes() == 0:
            print("\n🛑 No more fixable patterns found.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
