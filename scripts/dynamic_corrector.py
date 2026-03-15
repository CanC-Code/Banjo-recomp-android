import os
import re
import subprocess
import time

LOG_FILE = "Android/full_build_log.txt"
GRADLE_CMD = ["./gradlew", "assembleDebug", "--stacktrace"]

def run_build():
    print("\n🚀 Running Gradle build...")
    # Change to Android directory for the build command if needed, or run from root
    os.chdir("Android")
    with open("full_build_log.txt", "w") as log:
        process = subprocess.Popen(
            GRADLE_CMD,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True
        )
        process.wait()
    os.chdir("..")
    return process.returncode == 0

def apply_dynamic_fixes():
    print("🛠️ Analyzing build log for dynamic corrections...")
    log_path = LOG_FILE
    if not os.path.exists(log_path):
        print("❌ No build log found.")
        return 0

    with open(log_path, "r", encoding="utf-8") as f:
        log_data = f.read()

    fixes_applied = 0

    # -------------------------------------------------------------------------
    # RULE 1: Missing Struct/Type Definitions (e.g., sChVegetable)
    # Match: /path/to/file.c:15:59: error: unknown type name 'sChVegetable'
    # -------------------------------------------------------------------------
    unknown_type_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: unknown type name '([^']+)'")
    missing_types = {}

    for match in unknown_type_pattern.finditer(log_data):
        filepath = match.group(1).strip()
        type_name = match.group(2).strip()
        if filepath not in missing_types:
            missing_types[filepath] = set()
        missing_types[filepath].add(type_name)

    for filepath, types in missing_types.items():
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            injections = []
            for t in types:
                # N64 decomp types usually start with s, u, f, or are capitalized
                typedef_str = f"typedef struct {t} {t};\n"
                if typedef_str not in content:
                    injections.append(typedef_str)

            if injections:
                # Inject right after the last #include, or at the top of the file
                includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                insert_pos = includes[-1].end() if includes else 0
                
                header = "\n\n/* 🤖 AUTO-INJECTED BY DYNAMIC CORRECTOR */\n"
                new_content = content[:insert_pos] + header + "".join(injections) + content[insert_pos:]
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                print(f"  [+] Injected {len(injections)} missing types into {os.path.basename(filepath)}")
                fixes_applied += 1

    # -------------------------------------------------------------------------
    # RULE 2: Undeclared Identifiers (e.g., missing global variables)
    # Match: error: use of undeclared identifier 'D_80387FA8'
    # -------------------------------------------------------------------------
    undeclared_id_pattern = re.compile(r"(/[^\s:]+\.c):\d+:\d+: error: use of undeclared identifier '([^']+)'")
    missing_ids = {}

    for match in undeclared_id_pattern.finditer(log_data):
        filepath = match.group(1).strip()
        var_name = match.group(2).strip()
        
        # We only want to auto-fix global data arrays or decompiled generic variables
        if var_name.startswith("D_") or var_name.startswith("sCh"):
            if filepath not in missing_ids:
                missing_ids[filepath] = set()
            missing_ids[filepath].add(var_name)

    for filepath, var_names in missing_ids.items():
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            injections = []
            for v in var_names:
                decl_str = f"extern u8 {v}[];\n"
                if decl_str not in content:
                    injections.append(decl_str)

            if injections:
                includes = list(re.finditer(r"^#include.*$", content, re.MULTILINE))
                insert_pos = includes[-1].end() if includes else 0
                
                header = "\n\n/* 🤖 AUTO-INJECTED EXTERN DECLARATIONS */\n"
                new_content = content[:insert_pos] + header + "".join(injections) + content[insert_pos:]
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                print(f"  [+] Injected {len(injections)} externs into {os.path.basename(filepath)}")
                fixes_applied += 1

    return fixes_applied

def main():
    print("========================================")
    print("   DYNAMIC SOURCE CORRECTOR STARTING")
    print("========================================")
    
    max_iterations = 10
    iteration = 1
    
    while iteration <= max_iterations:
        print(f"\n--- Iteration {iteration} ---")
        success = run_build()
        
        if success:
            print("\n✅ Build succeeded! Dynamic compilation complete.")
            break
            
        print("❌ Build failed. Parsing logs for fixable errors...")
        fixes_made = apply_dynamic_fixes()
        
        if fixes_made == 0:
            print("\n⚠️ Build failed, and no fixable patterns were found in the log.")
            print("You will need to manually investigate the remaining errors.")
            break
            
        iteration += 1
        time.sleep(1) # Brief pause to ensure file system sync
        
    if iteration > max_iterations:
        print("\n🛑 Reached maximum iterations. Stopping to prevent infinite loops.")

if __name__ == "__main__":
    main()
