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
    
    # Existing Patterns
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    null_errs = re.findall(file_regex + r":(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'", log_data)
    
    # 🆕 Language Linkage Pattern (Fixes sinf/cosf errors)
    linkage_errs = re.findall(file_regex + r":\d+:\d+: error: declaration of '([^']+)' has a different language linkage", log_data)

    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", 
        "OSContPad", "Vtx", "Mtx", "ALHeap", "sched_yield", "M_PI", "ADPCM_STATE"
    }

    # Handle Linkage Errors
    for filepath, func_name in set(linkage_errs):
        if os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            header = "#include <math.h>\n" if func_name in ["sinf", "cosf", "sqrtf", "atan2f"] else ""
            if header and header not in content:
                with open(filepath, "w") as f: f.write(header + content)
                print(f"  [+] Injected {header.strip()} at top to fix linkage of {func_name}")
                fixes += 1

    # Handle Standard Errors
    affected_files = set([e[0] for e in type_errs] + [e[0] for e in id_errs] + [e[0] for e in null_errs])
    for filepath in [f for f in affected_files if os.path.exists(f) and "n64_types.h" not in f]:
        with open(filepath, "r") as f: content = f.read()
        original_content = content
        
        file_errors = [t[1] for t in type_errs if t[0] == filepath] + [i[1] for i in id_errs if i[0] == filepath]
        
        if any(err in CORE_N64 for err in file_errors):
            if 'include "ultra/n64_types.h"' not in content:
                content = '#include "ultra/n64_types.h"\n' + content
                print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
                fixes += 1
        
        for err in set(file_errors):
            if err.startswith(("D_", "sCh")):
                decl = f"extern u8 {err}[];\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected extern: {err}")
                    fixes += 1
            elif err not in CORE_N64 and not err.startswith(("D_", "sCh")):
                decl = f"typedef struct {err} {err};\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected struct typedef: {err}")
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
