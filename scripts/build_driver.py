import os
import subprocess
import time
import re
from source_conversion import SourceConverter
from error_parser import generate_failed_log, generate_error_summary, read_file

# --- Environment Configuration ---
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
MANIFEST_FILE   = "Android/fixed_files.log"
MAX_STALL       = 5

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def get_ninja_cmd():
    base_dir = "Android/app/.cxx/Debug"
    if os.path.exists(base_dir):
        for hash_dir in os.listdir(base_dir):
            ninja_dir = os.path.join(base_dir, hash_dir, "arm64-v8a")
            if os.path.exists(os.path.join(ninja_dir, "build.ninja")):
                return ["/usr/local/lib/android/sdk/cmake/3.22.1/bin/ninja", "-C", ninja_dir, "bkawrapper"]
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

def main():
    stall_count = 0
    converter = SourceConverter()

    # --- CRITICAL: HARD RESET FOR CYCLE 1 ---
    # This ensures we start with a clean Master Shield v24 and no "Layer Cake" header.
    print("🧹 Performing Initial Cleanse...")
    converter.bootstrap_n64_types(clear_existing=True) 
    
    for cycle in range(1, 401): 
        print(f"\n{'='*40}\n--- Cycle {cycle} ---\n{'='*40}")

        # Ensure the header is initialized (won't clear after Cycle 1)
        converter.bootstrap_n64_types(clear_existing=False)

        if run_build():
            print("\n✅ Build Successful!")
            return

        log_data = read_file(LOG_FILE)
        failed_files = generate_failed_log(log_data, FAILED_LOG_FILE)
        converter.load_logic()

        total_fixes_this_cycle = 0
        if failed_files:
            for file_path in failed_files:
                # We pass the log_data so GLOBAL_INJECT can find the Master Shield triggers
                fixes_applied = converter.apply_to_file(file_path, error_context=log_data)
                total_fixes_this_cycle += fixes_applied

        if total_fixes_this_cycle == 0:
            stall_count += 1
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted: No fixable patterns found.")
                break
        else:
            stall_count = 0 
        time.sleep(1)

if __name__ == "__main__":
    main()
