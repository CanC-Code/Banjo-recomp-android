import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
SDK_INCLUDE_DIR = "include"

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def harvest_macro(macro_name):
    if not os.path.exists(SDK_INCLUDE_DIR): return None
    for root, _, files in os.walk(SDK_INCLUDE_DIR):
        for file in files:
            if not file.endswith('.h'): continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
            except: continue
            for i, line in enumerate(lines):
                if re.match(rf'^[ \t]*#[ \t]*define[ \t]+{macro_name}\b', line):
                    macro_block = line
                    curr = i
                    while macro_block.strip().endswith('\\') and curr + 1 < len(lines):
                        curr += 1
                        macro_block += lines[curr]
                    return macro_block.strip()
    return None

def inject_to_header(block, name):
    if not os.path.exists(TYPES_HEADER): return False
    with open(TYPES_HEADER, "r") as f: content = f.read()
    if f"define {name}" in content or f"typedef" in content and f" {name}" in content:
        return False
    pos = content.rfind('#endif')
    if pos != -1:
        new_content = content[:pos] + f"\n/* Auto-Harvested */\n{block}\n\n" + content[pos:]
        with open(TYPES_HEADER, "w") as f: f.write(new_content)
        return True
    return False

def run_build():
    print("\n🚀 Starting Build Cycle...")
    if not os.path.exists("Android"): os.makedirs("Android")
    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            clean_line = strip_ansi(line)
            log.write(clean_line)
            print(clean_line, end="") 
        process.wait()
    return process.returncode == 0

def apply_fixes():
    if not os.path.exists(LOG_FILE): return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f: log_data = f.read()

    fixes = 0
    file_regex = r"(\S+\.[ch](?:pp)?)"
    CORE_N64 = {"__OSGlobalIntMask", "osClockRate", "osResetType", "osAppNMIBuffer", "Actor", "ActorMarker", "OSContPad", "ALHeap", "ALGlobals"}

    error_lines = [line for line in log_data.split('\n') if "error:" in line]
    affected_files = set()
    for line in error_lines:
        match = re.search(file_regex, line)
        if match: affected_files.add(match.group(1))

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue
        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # FIX A: The 'close' Conflict
        if "follows non-static declaration" in log_data or "lockup.c" in filepath:
            if "bka_close" not in content:
                content = re.sub(r'\bclose\b', 'bka_close', content)
                print(f"  [-] Renamed internal 'close' -> 'bka_close' in {os.path.basename(filepath)}")
                fixes += 1

        # FIX B: Intelligent Purifier (Only delete empty declarations, leave bodies alone)
        for symbol in CORE_N64:
            pattern = rf"^(?:extern|volatile|static|typedef)?\s+[^;{{}}]+\s+{re.escape(symbol)}\b[^;{{}}]*;"
            match = re.search(pattern, content, re.MULTILINE)
            if match and '{' not in match.group(0):
                content = re.sub(pattern, f"/* Authority Strategy Purge: {symbol} */", content, flags=re.MULTILINE)
                print(f"  [🪠] Purged local declaration of {symbol} in {os.path.basename(filepath)}")
                fixes += 1

        # FIX C: 'actor' pointer mismatch injection
        if "use of undeclared identifier 'actor'" in log_data and "this" in content:
            if "Actor *actor =" not in content:
                content = re.sub(r'(\{)', r'\1\n    Actor *actor = (Actor *)this;', content, count=1)
                print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
                fixes += 1

        # FIX D: Macro Harvesting
        missing_ids = re.findall(rf"{re.escape(filepath)}:\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
        for identifier in missing_ids:
            if identifier.isupper() or identifier.startswith("CH_"):
                macro = harvest_macro(identifier)
                if macro:
                    if inject_to_header(macro, identifier):
                        print(f"  [🤖] Harvested: {identifier}")
                        fixes += 1

        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            fixes += 1

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    return fixes

def main():
    for i in range(1, 100):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        if apply_fixes() == 0:
            print("\n🛑 Loop halted. No fixable patterns found.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
