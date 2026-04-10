import os
import subprocess
import time
import re
from source_conversion import SourceConverter
from error_parser import generate_failed_log, generate_error_summary, read_file

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "8"
if "NINJAJOBS" in os.environ:
    del os.environ["NINJAJOBS"]

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=8", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError",
]

LOG_FILE        = "Android/full_build_log.txt"
FAILED_LOG_FILE = "Android/failed_files.log"
MANIFEST_FILE   = "Android/fixed_files.log"
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

def resolve_cpp_path(file_path):
    if os.path.exists(file_path):
        return file_path
        
    # Strip potential absolute paths from runner logs
    if "Banjo-recomp-android/" in file_path:
        file_path = file_path.split("Banjo-recomp-android/")[-1]
        if os.path.exists(file_path):
            return file_path

    search_bases = ["Android/app/src/main/cpp", "src"]
    for base in search_bases:
        attempt = os.path.join(base, file_path)
        if os.path.exists(attempt):
            return attempt
            
    filename = os.path.basename(file_path)
    for base in search_bases:
        if not os.path.exists(base): 
            continue
        for root, _, files in os.walk(base):
            if filename in files:
                return os.path.join(root, filename)
    return file_path

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
    converter = SourceConverter()
    print("🧹 Performing Initial Cleanse...")
    converter.bootstrap_n64_types(clear_existing=True)
    converter.load_logic()

    print(f"\n{'='*40}\n--- Applying Initial Fixes ---\n{'='*40}")

    fixes_applied = converter.apply_to_file(TYPES_HEADER)
    print(f"🔧 Applied {fixes_applied} fixes to n64_types.h")

    # Sweep BOTH the Android wrapper AND the core game src folder
    source_dirs = ["Android/app/src/main/cpp", "src"]
    for base_dir in source_dirs:
        if not os.path.exists(base_dir):
            continue
        for root, _, files in os.walk(base_dir):
            for filename in files:
                filepath = os.path.join(root, filename)

                if filename.endswith(('.c', '.cpp')):
                    ensure_bridge_at_top(filepath)

                if filename.endswith(('.c', '.cpp', '.h')):
                    file_fixes = converter.apply_to_file(filepath)
                    if file_fixes > 0:
                        print(f"🔧 Applied {file_fixes} fixes to {filepath}")

    # The Iterative Build Loop (Self-Healing Core)
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

            with open(LOG_FILE, 'r', errors='replace') as f:
                log_content = f.read()

            # Scrape logs using the newly repurposed log scraper logic
            converter.scrape_logs(log_content)
            
            # Gather files needing dynamic intervention
            targeted_files = set()
            if hasattr(converter, 'dynamic_categories'):
                if "needs_float_fix" in converter.dynamic_categories:
                    targeted_files.update(converter.dynamic_categories["needs_float_fix"])
                if "needs_redef_strip" in converter.dynamic_categories:
                    targeted_files.update(converter.dynamic_categories["needs_redef_strip"])
            
            # Always check the main types header during self-healing
            targeted_files.add(TYPES_HEADER)

            print("\n🛠️ Applying Dynamic Self-Healing Fixes...")
            fixed_count = 0
            for file_path in targeted_files:
                resolved_path = resolve_cpp_path(file_path)
                if os.path.exists(resolved_path):
                    if resolved_path.endswith(('.c', '.cpp')):
                        ensure_bridge_at_top(resolved_path)
                    fixes = converter.apply_to_file(resolved_path)
                    if fixes > 0:
                        print(f"    🔧 Dynamically fixed: {resolved_path}")
                        fixed_count += fixes
            
            # Inject opaque bodies for unknown structs discovered in the log
            converter.apply_dynamic_fixes()

if __name__ == "__main__":
    main()
