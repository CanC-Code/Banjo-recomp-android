import os
import subprocess
import time
import re
from error_parser import classify_errors, generate_failed_log, generate_error_summary, read_file
from patch_engine import apply_fixes

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=1", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError",
    "-Pandroid.ndk.cmakeArgs=-k 0",
]

LOG_FILE        = "Android/full_build_log.txt"
FAILED_LOG_FILE = "Android/failed_files.log"
MAX_STALL       = 5

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def run_build():
    print("\n🚀 Starting Build Cycle...")
    os.makedirs("Android", exist_ok=True)
    with open(LOG_FILE, "w") as log:
        try:
            process = subprocess.Popen(
                GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
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

    for i in range(1, 200):
        print(f"\n{'='*40}\n--- Cycle {i} ---\n{'='*40}")

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

        # Step 2: Apply the fixes
        fixes, fixed_files = apply_fixes(categories)

        if fixes == 0:
            generate_error_summary(log_data)
            stall_count += 1
            print(f"\n⚠️  No fixable patterns this cycle. Stall count: {stall_count}/{MAX_STALL}")
            if failed_files: print(f"   {len(failed_files)} file(s) still failing — see {FAILED_LOG_FILE}")
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted after {MAX_STALL} consecutive stall cycles.")
                break
        else:
            print(f"\n  ✅ Applied {fixes} fix(es) across {len(fixed_files)} source file(s) this cycle.")
            stall_count = 0

        time.sleep(1)

if __name__ == "__main__":
    main()
