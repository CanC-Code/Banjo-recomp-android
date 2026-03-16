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
    
    # Known Patterns
    type_errs = re.findall(r"(/[^\s:]+\.c):\d+:\d+: error: unknown type name '([^']+)'", log_data)
    null_errs = re.findall(r"(/[^\s:]+\.c):(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'", log_data)
    id_errs = re.findall(r"(/[^\s:]+\.c):\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)

    # Apply Known Fixes
    for filepath, t_name in set(type_errs):
        if os.path.exists(filepath):
            with open(filepath, "r") as f: content = f.read()
            decl = f"typedef struct {t_name} {t_name};\n"
            if decl not in content:
                with open(filepath, "w") as f: f.write(decl + content)
                print(f"  [+] Injected type: {t_name}")
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
                
    # DIAGNOSTIC MODE: If no fixes were applied, find out what the actual errors are
    if fixes == 0:
        print("\n⚠️ Build failed but no known fix patterns matched.")
        print("🔍 Searching for unhandled compiler errors...")
        unhandled_errors = re.findall(r"error: (.*)", log_data)
        
        if unhandled_errors:
            print("\n🚨 UNHANDLED ERRORS DETECTED (Showing first 5):")
            for err in list(dict.fromkeys(unhandled_errors))[:5]: # Deduplicate and show top 5
                print(f"  - {err}")
        else:
            print("  - Could not parse specific C/C++ errors. The build might be failing at the linker stage.")

    return fixes

def main():
    for i in range(1, 16):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        
        applied_fixes = apply_fixes()
        if applied_fixes == 0:
            print("\n🛑 Halting loop. Please share the UNHANDLED ERRORS printed above so we can write a fix pattern for them.")
            break
        
        print(f"🛠️ Applied {applied_fixes} fixes. Restarting compiler...")
        time.sleep(1)

if __name__ == "__main__":
    main()
