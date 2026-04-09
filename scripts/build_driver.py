import os
import subprocess
import time
import re
from source_conversion import SourceConverter
from error_parser import generate_failed_log, generate_error_summary, read_file

# THE FIX: Unleash parallel processing so we can patch hundreds of files in one cycle
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
MAX_STALL       = 5

def strip_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def get_ninja_cmd():
    base_dir = "Android/app/.cxx/Debug"
    if os.path.exists(base_dir):
        for hash_dir in os.listdir(base_dir):
            ninja_dir = os.path.join(base_dir, hash_dir, "arm64-v8a")
            if os.path.exists(os.path.join(ninja_dir, "build.ninja")):
                # THE FIX: -k 0 forces Ninja to keep going and gather ALL failing files at once
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
    """Resolves relative compiler paths to absolute source tree paths."""
    if os.path.exists(file_path):
        return file_path
    
    cpp_base = "Android/app/src/main/cpp"
    attempt = os.path.join(cpp_base, file_path)
    if os.path.exists(attempt):
        return attempt
        
    filename = os.path.basename(file_path)
    for root, _, files in os.walk(cpp_base):
        if filename in files:
            return os.path.join(root, filename)
            
    return file_path

def ensure_bridge_at_top(file_path):
    """Forces the Master Shield bridge to Line 1 so SDK headers don't crash."""
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
    stall_count = 0
    converter = SourceConverter()

    print("🧹 Performing Initial Cleanse...")
    converter.bootstrap_n64_types(clear_existing=True) 
    converter.load_logic()

    for cycle in range(1, 401): 
        print(f"\n{'='*40}\n--- Cycle {cycle} ---\n{'='*40}")

        if run_build():
            print("\n✅ Build Successful!")
            return

        log_data = read_file(LOG_FILE)
        failed_files = generate_failed_log(log_data, FAILED_LOG_FILE)

        total_fixes_this_cycle = 0
        if failed_files:
            trigger_pattern = r"unknown type name '(?:OSMesg|OSTime|OSPri|OSId|OSTask|Mtx|Gfx|Acmd|ADPCM_STATE|u32|u16|u8|s32|f32|f64|ALFilter|ALCmdHandler|ALSeq|ALCSeq)'|undeclared identifier '(?:m|l)'|expected '\(' for function-style cast"

            if re.search(trigger_pattern, log_data):
                print("🛡️ Master Shield Trigger Detected: Routing to n64_types.h")
                fixes_applied = converter.apply_to_file(TYPES_HEADER, error_context=log_data)
                total_fixes_this_cycle += fixes_applied

            for raw_path in failed_files:
                file_path = resolve_cpp_path(raw_path) 
                if file_path != TYPES_HEADER: 
                    bridge_added = ensure_bridge_at_top(file_path)
                    fixes_applied = converter.apply_to_file(file_path, error_context=log_data)
                    total_fixes_this_cycle += fixes_applied + (1 if bridge_added else 0)

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
