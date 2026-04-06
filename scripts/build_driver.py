import os
import subprocess
import time
import re
from error_parser import classify_errors, generate_failed_log, generate_error_summary, read_file
from patch_engine import apply_fixes

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

# Fallback Gradle command if Ninja cannot be located
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
PHASE_SHIFT_STALL = 2

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def get_ninja_cmd():
    """Attempts to locate the dynamic Ninja build directory to skip Gradle overhead."""
    base_dir = "Android/app/.cxx/Debug"
    if os.path.exists(base_dir):
        # Scan for the generated CMake hash directory
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
    intelligence_level = 1
    
    # Ensure manifest file exists
    os.makedirs("Android", exist_ok=True)
    if not os.path.exists(MANIFEST_FILE):
        open(MANIFEST_FILE, 'w').close()

    for i in range(1, 400):  # Expanded range to allow for deeper compiling
        print(f"\n{'='*40}\n--- Cycle {i} | Intelligence Level: {intelligence_level} ---\n{'='*40}")

        if run_build():
            print("\n✅ Build Successful!")
            if os.path.exists(FAILED_LOG_FILE): os.remove(FAILED_LOG_FILE)
            return

        if not os.path.exists(LOG_FILE): 
            print("❌ No log file found, stopping.")
            break

        log_data = read_file(LOG_FILE)

        # Step 1: Parse the errors
        categories = classify_errors(log_data)
        failed_files = generate_failed_log(log_data, FAILED_LOG_FILE)

        # Phase Shift Logic: Upgrade intelligence if stuck at Level 1
        if stall_count >= PHASE_SHIFT_STALL and intelligence_level == 1:
            print("\n🧠 Leveling up intelligence... Transitioning to Level 2 (Advanced I/O & Structs).")
            intelligence_level = 2
            stall_count = 0  # Reset stall count for the new phase
            
        # Step 2: Apply the fixes with our current intelligence state
        # Note: We are now passing `intelligence_level` to the patch engine.
        fixes, fixed_files = apply_fixes(categories, intelligence_level)

        if fixes == 0:
            generate_error_summary(log_data)
            stall_count += 1
            print(f"\n⚠️  No fixable patterns this cycle. Stall count: {stall_count}/{MAX_STALL}")
            if failed_files: print(f"   {len(failed_files)} file(s) still failing — see {FAILED_LOG_FILE}")
            
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted after {MAX_STALL} consecutive stall cycles at Max Intelligence.")
                break
        else:
            print(f"\n  ✅ Applied {fixes} fix(es) across {len(fixed_files)} source file(s) this cycle.")
            
            # Lock in fixed files
            with open(MANIFEST_FILE, "a") as mf:
                for f in fixed_files:
                    mf.write(f"{f}\n")
                    
            stall_count = 0

        time.sleep(1)

if __name__ == "__main__":
    main()
