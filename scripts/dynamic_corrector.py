import os
import re
import subprocess
import time

# Use the global 'gradle' command for GitHub Actions environment
GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"

def run_build():
    print("\n🚀 Starting build cycle...")
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(
            GRADLE_CMD,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True
        )
        process.wait()
    return process.returncode == 0

def apply_dynamic_fixes():
    print("🛠️ Analyzing build log for compiler errors...")
    if not os.path.exists(LOG_FILE):
        return 0

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_data = f.read()

    fixes_applied = 0

    # --- 1. Fix: Unknown Type Names (e.g. sChVegetable) ---
    # Pattern: file.c:line:col: error: unknown type name 'Name'
    type_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: unknown type name '([^']+)'")
    missing_types = {}
    for match in type_pattern.finditer(log_data):
        filepath, type_name = match.groups()
        if filepath not in missing_types: missing_types[filepath] = set()
        missing_types[filepath].add(type_name)

    for filepath, types in missing_types.items():
        if os.path.exists(filepath):
            with open(filepath, "r") as f: lines = f.readlines()
            # Inject forward declarations at the very top of the file
            injections = [f"typedef struct {t} {t};\n" for t in types if f"typedef struct {t}" not in "".join(lines[:50])]
            if injections:
                lines = injections + ["\n/* 🤖 AUTO-TYPE-INJECT */\n"] + lines
                with open(filepath, "w") as f: f.writelines(lines)
                print(f"  [+] Injected types into {os.path.basename(filepath)}")
                fixes_applied += 1

    # --- 2. Fix: NULL-to-Float Incompatibility ---
    # Pattern: file.c:line:col: error: initializing 'f32' ... with incompatible type 'void *'
    # This detects the line number to prevent corrupting other parts of the file.
    null_pattern = re.compile(r"(/[^\s:]+\.c):(\d+):\d+: error: initializing 'f32' .* incompatible type 'void \*'")
    for match in null_pattern.finditer(log_data):
        filepath, line_num = match.groups()
        line_idx = int(line_num) - 1
        if os.path.exists(filepath):
            with open(filepath, "r") as f: lines = f.readlines()
            if line_idx < len(lines) and "NULL" in lines[line_idx]:
                # Replace NULL with 0 (valid for floats and pointers) on that specific line
                lines[line_idx] = lines[line_idx].replace("NULL", "0")
                with open(filepath, "w") as f: f.writelines(lines)
                print(f"  [+] Patched NULL float on line {line_num} of {os.path.basename(filepath)}")
                fixes_applied += 1

    # --- 3. Fix: Undeclared Identifiers ---
    # Pattern: file.c:line:col: error: use of undeclared identifier 'D_...'
    id_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: use of undeclared identifier '([^']+)'")
    missing_ids = {}
    for match in id_pattern.finditer(log_data):
        filepath, var_name = match.groups()
        if var_name.startswith(("D_", "sCh")):
            if filepath not in missing_ids: missing_ids[filepath] = set()
            missing_ids[filepath].add(var_name)

    for filepath, var_names in missing_ids.items():
        if os.path.exists(filepath):
            with open(filepath, "r") as f: lines = f.readlines()
            injections = [f"extern u8 {v}[];\n" for v in var_names if v not in "".join(lines[:100])]
            if injections:
                lines = injections + ["\n/* 🤖 AUTO-EXTERN-INJECT */\n"] + lines
                with open(filepath, "w") as f: f.writelines(lines)
                print(f"  [+] Injected externs into {os.path.basename(filepath)}")
                fixes_applied += 1

    return fixes_applied

def main():
    max_cycles = 15
    for i in range(1, max_cycles + 1):
        print(f"\n--- Correction Cycle {i} ---")
        if run_build():
            print("\n✅ Build Passed!")
            return
        
        if apply_dynamic_fixes() == 0:
            print("\n⚠️ No more fixable patterns detected. Check logs for logic errors.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
