"""
build_driver.py — Self-healing build driver for the BK AArch64 Android port.
This orchestrates the SourceConverter to dynamically parse error logs,
inject structs, resolve POSIX conflicts, and bootstrap SDK types.
"""

import os
import subprocess
import time
import re
from source_conversion import SourceConverter
from error_parser import generate_failed_log, generate_error_summary, read_file

# --- Environment Configuration ---
os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

# Gradle configuration for Android build
GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=1", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError",
    "-Pandroid.ndk.cmakeArgs=-k 0",
]

LOG_FILE        = "Android/full_build_log.txt"
FAILED_LOG_FILE = "Android/failed_files.log"
MANIFEST_FILE   = "Android/fixed_files.log"
MAX_STALL       = 5

def strip_ansi(text):
    """Removes terminal color codes from logs."""
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def get_ninja_cmd():
    """Attempts to locate the Ninja build directory to skip Gradle overhead."""
    base_dir = "Android/app/.cxx/Debug"
    if os.path.exists(base_dir):
        for hash_dir in os.listdir(base_dir):
            ninja_dir = os.path.join(base_dir, hash_dir, "arm64-v8a")
            if os.path.exists(os.path.join(ninja_dir, "build.ninja")):
                return [
                    "/usr/local/lib/android/sdk/cmake/3.22.1/bin/ninja",
                    "-C", ninja_dir,
                    "bkawrapper"
                ]
    return GRADLE_CMD

def run_build():
    """Executes the build command and streams logs to file and console."""
    cmd = get_ninja_cmd()
    tool_name = "Ninja" if "ninja" in cmd[0] else "Gradle"
    print(f"\n🚀 Starting Build Cycle via {tool_name}...")
    os.makedirs("Android", exist_ok=True)

    with open(LOG_FILE, "w") as log:
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in process.stdout:
                clean_line = strip_ansi(line)
                log.write(clean_line)
                print(clean_line, end="")
            process.wait()
            return process.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}")
            return False

def main():
    stall_count = 0
    converter = SourceConverter()

    # Ensure manifest file exists to track progress
    os.makedirs("Android", exist_ok=True)
    if not os.path.exists(MANIFEST_FILE):
        open(MANIFEST_FILE, 'w').close()

    for cycle in range(1, 401):  # Loop through cycles
        print(f"\n{'='*40}\n--- Cycle {cycle} ---\n{'='*40}")

        # Bootstrap essential N64 primitive mappings (stdint.h, u32, f32)
        # before the compiler is invoked, replicating dynamic_corrector.py's safety net
        if hasattr(converter, 'bootstrap_n64_types'):
            converter.bootstrap_n64_types()

        # Attempt to build
        if run_build():
            print("\n✅ Build Successful! Target APK generated.")
            if os.path.exists(FAILED_LOG_FILE): os.remove(FAILED_LOG_FILE)
            return

        # If build fails, analyze the logs
        if not os.path.exists(LOG_FILE): 
            print("❌ No log file found, stopping.")
            break

        log_data = read_file(LOG_FILE)
        failed_files = generate_failed_log(log_data, FAILED_LOG_FILE)

        # Dynamically load ALL rules defined in external text databases.
        # Placed here so you can add new logic files mid-execution without restarting!
        converter.load_logic()

        total_fixes_this_cycle = 0
        files_affected = set()

        # Apply fixes to files causing failures. We pass both the file path AND 
        # the full log data so the converter can hunt for Macros/Stubs effectively!
        if failed_files:
            print(f"🧐 Targeting {len(failed_files)} failing file(s)...")
            for file_path in failed_files:
                fixes_applied = converter.apply_to_file(file_path, error_context=log_data)
                if fixes_applied > 0:
                    total_fixes_this_cycle += fixes_applied
                    files_affected.add(file_path)

        # Handle stalling
        if total_fixes_this_cycle == 0:
            generate_error_summary(log_data)
            stall_count += 1
            print(f"\n⚠️  No fixable patterns found. Stall count: {stall_count}/{MAX_STALL}")

            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted: No matching logic found for these errors.")
                break
        else:
            print(f"\n✨ Applied {total_fixes_this_cycle} fix(es) across {len(files_affected)} file(s).")

            # Log progress to manifest
            with open(MANIFEST_FILE, "a") as mf:
                for f in files_affected:
                    mf.write(f"Cycle {cycle}: Fixed {f}\n")

            stall_count = 0 # Reset stall on success

        time.sleep(1)

if __name__ == "__main__":
    main()
