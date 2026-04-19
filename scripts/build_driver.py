import os
import subprocess
import re

# Import the new functional engine from source_conversion.py
from source_conversion import apply_fixes, ensure_types_header_base

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "8"
if "NINJAJOBS" in os.environ:
    del os.environ["NINJAJOBS"]

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=8", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError",
]

LOG_FILE        = "Android/full_build_log.txt"
TYPES_HEADER    = "Android/app/src/main/cpp/ultra/n64_types.h"

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def get_ninja_cmd():
    base_dir = "Android/app/.cxx/Debug"
    if os.path.exists(base_dir):
        for hash_dir in os.listdir(base_dir):
            ninja_dir = os.path.join(base_dir, hash_dir, "arm64-v8a")
            if os.path.exists(os.path.join(ninja_dir, "build.ninja")):
                return ["/usr/local/lib/android/sdk/cmake/3.22.1/bin/ninja", "-C", ninja_dir, "-k", "0", "bkawrapper"]
    return GRADLE_CMD

def run_build():
    cmd = get_ninja_cmd()
    print(f"\n🚀 Starting Build Cycle...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w") as log:
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                clean_line = strip_ansi(line)
                log.write(clean_line)
                print(clean_line, end="")
            process.wait()
            return process.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}")
            return False

def ensure_bridge_included(file_path):
    """
    Validates inclusion without aggressively destroying include order.
    Appends after standard library includes if insertion is necessary.
    """
    if not os.path.exists(file_path) or file_path.endswith('.h') or "n64_types.h" in file_path:
        return False
        
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        
    # Skip if already included anywhere in the file to preserve developer intent
    if re.search(r'#include\s+["<](?:ultra/)?n64_types\.h[">]', content):
        return False

    # Insert safely after any standard library includes, or at the top if none exist
    bridge = '#include "ultra/n64_types.h"\n'
    
    last_std_include = list(re.finditer(r'#include\s+<[^>]+>\n', content))
    if last_std_include:
        insert_pos = last_std_include[-1].end()
        new_content = content[:insert_pos] + bridge + content[insert_pos:]
    else:
        new_content = bridge + content
        
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"    🌉 Safely injected Bridge Header into {file_path}")
    return True

def main():
    print("🧹 Performing Initial Cleanse...")

    # State Context Dictionary: Elevated to persist across the entire pipeline execution
    # This ensures previous fixes and parsed macros are not destroyed between loops.
    global_context_categories = {}

    # Initial type generation using the preserved context
    ensure_types_header_base(global_context_categories)

    print(f"\n{'='*40}\n--- Applying Initial Fixes ---\n{'='*40}")

    # Seed the initial structural types and macros
    fixes_applied, fixed_files = apply_fixes(global_context_categories, intelligence_level=3)
    print(f"🔧 Applied {fixes_applied} structural definition fixes.")

    # Sweep source files to ensure the bridge header is available globally
    source_dirs = ["Android/app/src/main/cpp", "src"]
    for base_dir in source_dirs:
        if not os.path.exists(base_dir):
            continue
        for root, _, files in os.walk(base_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                if filename.endswith(('.c', '.cpp')):
                    ensure_bridge_included(filepath)

    # === Iterative self-healing loop ===
    max_iterations = 4
    for iteration in range(1, max_iterations + 1):
        if run_build():
            print("\n✅ Build Successful!")
            break
        else:
            print(f"\n❌ Build Failed (Iteration {iteration}/{max_iterations}). Analyzing logs...")

            if iteration == max_iterations:
                print("🛑 Maximum build iterations reached. Halting.")
                break

            print("\n🛠️ Applying Dynamic Self-Healing Fixes...")

            # Utilizing the persistent global_context_categories to prevent cyclical regression
            fixes, modded_files = apply_fixes(global_context_categories, intelligence_level=3)

            # Re-sync the base types header in case apply_fixes discovered new structural dependencies
            ensure_types_header_base(global_context_categories)

            print(f"    🔧 Dynamically applied {fixes} syntax/macro fixes across {len(modded_files)} files.")

if __name__ == "__main__":
    main()
