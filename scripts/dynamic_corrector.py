import os
import re
import subprocess
import time

# Use the global 'gradle' command provided by the GitHub Action
# -p Android tells gradle to look for the project in the Android folder
GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"

def run_build():
    print("\n🚀 Running Gradle build cycle...")
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
    print("🛠️ Analyzing build log for dynamic corrections...")
    if not os.path.exists(LOG_FILE):
        print(f"❌ No build log found at {LOG_FILE}.")
        return 0

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_data = f.read()

    fixes_applied = 0

    # 1. Detect "timespec" redefinition - This requires manual header intervention
    if "redefinition of 'timespec'" in log_data:
        print("⚠️  CRITICAL: 'timespec' redefinition detected.")
        print("    Please ensure Android/app/src/main/cpp/ultra/n64_types.h includes <time.h> FIRST.")

    # 2. Pattern for unknown type names (e.g., 'sChVegetable', 'Actor')
    unknown_type_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: unknown type name '([^']+)'")
    
    # 3. Pattern for undeclared identifiers (e.g., 'D_80387FA8')
    undeclared_id_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: use of undeclared identifier '([^']+)'")
    
    # 4. Pattern for NULL-to-float assignment (Modern Clang restriction)
    # Match: initializing 'f32' (aka 'float') with an expression of incompatible type 'void *'
    null_float_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: initializing 'f32' .* incompatible type 'void \*'")

    # --- Processing Types ---
    missing_types = {}
    for match in unknown_type_pattern.finditer(log_data):
        filepath, type_name = match.groups()
        if filepath not in missing_types: missing_types[filepath] = set()
        missing_types[filepath].add(type_name)

    for filepath, types in missing_types.items():
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f: content = f.read()
            injections = [f"typedef struct {t} {t};\n" for t in types if f"typedef struct {t}" not in content]
            if injections:
                includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                pos = includes[-1].end() if includes else 0
                new_content = content[:pos] + "\n\n/* 🤖 AUTO-TYPE-INJECT */\n" + "".join(injections) + content[pos:]
                with open(filepath, "w", encoding="utf-8") as f: f.write(new_content)
                print(f"  [+] Injected {len(injections)} types into {os.path.basename(filepath)}")
                fixes_applied += 1

    # --- Processing Externs ---
    missing_ids = {}
    for match in undeclared_id_pattern.finditer(log_data):
        filepath, var_name = match.groups()
        if var_name.startswith(("D_", "sCh")):
            if filepath not in missing_ids: missing_ids[filepath] = set()
            missing_ids[filepath].add(var_name)

    for filepath, var_names in missing_ids.items():
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f: content = f.read()
            injections = [f"extern u8 {v}[];\n" for v in var_names if v not in content]
            if injections:
                includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                pos = includes[-1].end() if includes else 0
                new_content = content[:pos] + "\n\n/* 🤖 AUTO-EXTERN-INJECT */\n" + "".join(injections) + content[pos:]
                with open(filepath, "w", encoding="utf-8") as f: f.write(new_content)
                print(f"  [+] Injected {len(injections)} externs into {os.path.basename(filepath)}")
                fixes_applied += 1

    # --- Processing NULL Floats ---
    for match in null_float_pattern.finditer(log_data):
        filepath = match.group(1).strip()
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f: content = f.read()
            # Replace {NULL, NULL} or similar initializers with 0.0f
            # This is a broad-stroke fix for the specific decompiler artifact
            if "NULL" in content:
                new_content = content.replace("NULL", "0") # 0 is valid for both pointers and floats
                with open(filepath, "w", encoding="utf-8") as f: f.write(new_content)
                print(f"  [+] Patched NULL-float initializer in {os.path.basename(filepath)}")
                fixes_applied += 1

    return fixes_applied

def main():
    max_iterations = 15
    print("==========================================")
    print("   DYNAMIC BUILD & CORRECTOR ENGINE      ")
    print("==========================================")
    
    for i in range(1, max_iterations + 1):
        print(f"\n--- Cycle {i} of {max_iterations} ---")
        if run_build():
            print("\n✅ Success! All C/C++ files compiled.")
            return

        fixes = apply_dynamic_fixes()
        if fixes == 0:
            print("\n⚠️  No fixable patterns found. Stopping loop.")
            break
        
        print(f"♻️  Applied {fixes} fixes. Retrying build...")
        time.sleep(1)

    print("\n❌ Build sequence ended. Check the latest full_build_log.txt for remaining errors.")

if __name__ == "__main__":
    main()
