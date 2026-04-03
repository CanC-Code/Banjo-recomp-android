import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

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
    
    # 1. Capture standard errors
    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    
    # 2. Capture TYPE MISMATCH errors (The Volatile Problem)
    # Pattern: file.c:line:col: error: redefinition of 'var' with a different type: 'new_type' vs 'old_type'
    mismatch_errs = re.findall(file_regex + r":\d+:\d+: error: redefinition of '([^']+)' with a different type: '([^']+)' vs '([^']+)'", log_data)

    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "OSIntMask",
        "__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer"
    }

    # Handle Mismatches by Harmonizing the Source to the Header
    for filepath, var_name, new_type, old_type in mismatch_errs:
        if var_name in CORE_N64 and os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            
            # We want the source to match our header's simple 'u32' or 'OSTime'
            # This regex looks for the declaration in the source and strips 'volatile' 
            # or aligns the type names.
            target_type = "u32" if "uint32" in old_type.lower() else old_type
            
            # Pattern to find: [optional volatile] [old_type] [var_name]
            pattern = rf"(volatile\s+)?{re.escape(new_type.replace('volatile ', ''))}\s+{re.escape(var_name)}"
            replacement = f"{target_type} {var_name}"
            
            new_content = re.sub(pattern, replacement, content)
            
            if new_content != content:
                with open(filepath, "w") as f: f.write(new_content)
                print(f"  [🛠️] Harmonized type for '{var_name}' in {os.path.basename(filepath)}")
                fixes += 1

    # ... (Rest of your existing sanitation and inclusion logic) ...
    # Ensure you keep the logic that forces n64_types.h into affected files
    
    affected_files = set([e[0] for e in type_errs] + [e[0] for e in id_errs])
    for filepath in affected_files:
        if not os.path.exists(filepath): continue
        with open(filepath, "r") as f: content = f.read()
        if 'include "ultra/n64_types.h"' not in content:
            with open(filepath, "w") as f: 
                f.write('#include "ultra/n64_types.h"\n' + content)
            print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
            fixes += 1

    return fixes

def main():
    for i in range(1, 50): # Cycles
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
