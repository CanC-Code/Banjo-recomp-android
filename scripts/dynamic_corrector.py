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
    null_errs = re.findall(file_regex + r":(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'", log_data)

    # Core N64 OS and Scalar types
    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", 
        "OSContPad", "Vtx", "Mtx", "ALHeap", "sched_yield", "M_PI", "ADPCM_STATE"
    }

    ID_TO_HEADER = {
        "timespec": "#define _POSIX_C_SOURCE 199309L\n#include <time.h>\n",
        "uintptr_t": "#include <stdint.h>\n",
        "size_t": "#include <stddef.h>\n",
        "memcpy": "#include <string.h>\n"
    }

    # Filter out system headers from the fix list to prevent circularity
    affected_files = set([e[0] for e in type_errs] + [e[0] for e in id_errs] + [e[0] for e in null_errs])
    project_files = [f for f in affected_files if not f.startswith(("/usr/", "/include/")) and "n64_types.h" not in f]

    for filepath in project_files:
        if not os.path.exists(filepath): continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content
        
        file_errors = ([t[1] for t in type_errs if t[0] == filepath] + 
                       [i[1] for i in id_errs if i[0] == filepath])
        
        # 1. Force N64 Master Header for OS types
        if any(err in CORE_N64 for err in file_errors):
            if 'include "ultra/n64_types.h"' not in content:
                content = '#include "ultra/n64_types.h"\n' + content
                print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
                fixes += 1
        
        # 2. Handle specific identifiers and externs
        for err in set(file_errors):
            if err in ID_TO_HEADER:
                h = ID_TO_HEADER[err]
                if h not in content:
                    content = h + content
                    print(f"  [+] Injected {h.strip()} for {err}")
                    fixes += 1
            elif err.startswith(("D_", "sCh")):
                decl = f"extern u8 {err}[];\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected extern: {err}")
                    fixes += 1
            elif err not in CORE_N64 and not err.startswith(("D_", "sCh")):
                # Generic struct typedef for unknown project structures
                decl = f"typedef struct {err} {err};\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected struct typedef: {err}")
                    fixes += 1

        # 3. Fix NULL-to-Float
        file_nulls = [n[1] for n in null_errs if n[0] == filepath]
        if file_nulls:
            lines = content.splitlines()
            for line_str in file_nulls:
                idx = int(line_str) - 1
                if idx < len(lines) and "NULL" in lines[idx]:
                    lines[idx] = lines[idx].replace("NULL", "0")
                    fixes += 1
            content = "\n".join(lines) + "\n"

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    if fixes == 0:
        print("\n⚠️ Checking for unhandled errors...")
        unhandled = re.findall(r"error: (.*)", log_data)
        if unhandled:
            print("\n🚨 UNHANDLED:")
            for err in list(dict.fromkeys(unhandled))[:5]: print(f"  - {err}")
                
    return fixes

def main():
    for i in range(1, 30):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        if apply_fixes() == 0:
            print("\n🛑 Loop halted. No fixable patterns found.")
            break
        print(f"🛠️ Cycle {i} complete. Restarting...")
        time.sleep(1)

if __name__ == "__main__":
    main()
