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

def ensure_bridge_at_top(file_path):
    if not os.path.exists(file_path) or file_path.endswith('.h') or "n64_types.h" in file_path:
        return False
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    bridge = '#include "ultra/n64_types.h"'
    if content.strip().startswith(bridge):
        return False
    content = re.sub(r'#include\s+["<](?:ultra/)?n64_types\.h[">]\n?', '', content)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(f"{bridge}\n{content}")
    print(f"    🌉 Forced Bridge Header to absolute top of {file_path}")
    return True

def main():
    print("🧹 Performing Initial Cleanse...")

    # === FRESH n64_types.h Generation ===
    # Provide an empty dictionary since we don't have log categories yet
    ensure_types_header_base({})

    print(f"\n{'='*40}\n--- Applying Initial Fixes ---\n{'='*40}")

    # Seed the initial structural types and macros (Level 3 unlocks all advanced structs)
    fixes_applied, fixed_files = apply_fixes({}, intelligence_level=3)
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
                    ensure_bridge_at_top(filepath)

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

            # The functional engine automatically parses the logs and targets the broken files
            categories = {}
            fixes, modded_files = apply_fixes(categories, intelligence_level=3)

            print(f"    🔧 Dynamically applied {fixes} syntax/macro fixes across {len(modded_files)} files.")

if __name__ == "__main__":
    main()
