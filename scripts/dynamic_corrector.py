import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def run_build():
    print("\n🚀 Starting Build Cycle...")
    if not os.path.exists("Android"):
        os.makedirs("Android")
    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(
            GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        for line in process.stdout:
            clean_line = strip_ansi(line)
            log.write(clean_line)
            print(clean_line, end="")
        process.wait()
    return process.returncode == 0

def classify_errors(log_data):
    """
    Returns a dict of recognized error categories found in the log.
    Each category maps to a list of relevant context strings.
    """
    categories = {
        "missing_n64_types": [],   # file needs n64_types.h include
        "actor_pointer": [],       # 'actor' undeclared in a TU
        "libaudio_types": [],      # Acmd / ADPCM_STATE missing (header-level, not per-file)
        "unknown": [],
    }

    # Header-level libaudio errors — these are always in libaudio.h itself,
    # not in individual TUs. Flag them so the loop can halt with a clear message
    # instead of spinning forever.
    libaudio_patterns = [
        r"libaudio\.h.*unknown type name 'Acmd'",
        r"libaudio\.h.*unknown type name 'ADPCM_STATE'",
    ]
    for pattern in libaudio_patterns:
        if re.search(pattern, log_data):
            categories["libaudio_types"].append(pattern)

    file_regex = r"(/[^:\s]+):"
    for line in log_data.split('\n'):
        if "error:" not in line:
            continue
        match = re.search(file_regex, line)
        filepath = match.group(1) if match else None

        if "unknown type name 'Acmd'" in line or "unknown type name 'ADPCM_STATE'" in line:
            # Already captured above at header level; skip per-file noise.
            pass
        elif "use of undeclared identifier 'actor'" in line and filepath:
            categories["actor_pointer"].append(filepath)
        elif filepath and os.path.exists(filepath):
            categories["missing_n64_types"].append(filepath)
        else:
            categories["unknown"].append(line.strip())

    return categories

def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_data = f.read()

    categories = classify_errors(log_data)
    fixes = 0

    # ── HALT CONDITION: libaudio header-level type errors ─────────────────────
    # These errors originate inside libaudio.h itself because _GBI_H_ suppresses
    # the gbi.h definitions that libaudio.h depends on (Acmd, ADPCM_STATE).
    # The fix belongs in n64_types.h (stub those types before #include libaudio.h),
    # NOT in individual TU files. Continuing the loop cannot resolve this.
    if categories["libaudio_types"]:
        print("\n🛑 HEADER-LEVEL ERRORS DETECTED in libaudio.h:")
        print("   → unknown type name 'Acmd' and/or 'ADPCM_STATE'")
        print("   Root cause: _GBI_H_ guard blocks gbi.h, which defines these types.")
        print("   Fix required in n64_types.h: add Acmd and ADPCM_STATE stubs")
        print("   BEFORE the '#include <PR/libaudio.h>' line.")
        print("   The corrector loop cannot resolve header-level type errors automatically.")
        return -1  # Sentinel: signals main() to halt immediately

    # ── FIX A: Priority Inclusion ──────────────────────────────────────────────
    affected_files = set(categories["missing_n64_types"])
    for filepath in affected_files:
        if not os.path.exists(filepath):
            continue
        if "/usr/include" in filepath or "ndk" in filepath:
            continue
        with open(filepath, "r") as f:
            content = f.read()
        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            with open(filepath, "w") as f:
                f.write(content)
            print(f"  [🛠️] Injected n64_types.h include into {os.path.basename(filepath)}")
            fixes += 1

    # ── FIX B: 'actor' pointer injection ──────────────────────────────────────
    if categories["actor_pointer"]:
        actor_files = set(categories["actor_pointer"])
        for filepath in actor_files:
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            original = content
            if "Actor *actor =" not in content and "this" in content:
                content = re.sub(
                    r'(\{)',
                    r'\1\n    Actor *actor = (Actor *)this;',
                    content,
                    count=1
                )
                print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
            if content != original:
                with open(filepath, "w") as f:
                    f.write(content)
                fixes += 1

    # ── UNKNOWN errors: report but don't fix ──────────────────────────────────
    if categories["unknown"] and fixes == 0:
        print("\n⚠️  Unrecognized errors (no automatic fix available):")
        for msg in categories["unknown"][:10]:
            print(f"   {msg}")

    return fixes

def main():
    for i in range(1, 100):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return

        result = apply_fixes()

        if result == -1:
            # Header-level error; looping is useless.
            print("\n🛑 Loop halted. Manual fix required in n64_types.h.")
            break
        elif result == 0:
            print("\n🛑 Loop halted. No fixable patterns found.")
            break

        time.sleep(1)

if __name__ == "__main__":
    main()
