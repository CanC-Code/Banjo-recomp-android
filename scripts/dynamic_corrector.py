import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"

def run_build():
    print("\n🚀 Starting Build Cycle...")
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir): os.makedirs(log_dir)

    with open(LOG_FILE, "w") as log:
        process = subprocess.Popen(GRADLE_CMD, stdout=log, stderr=subprocess.STDOUT, text=True)
        process.wait()
    return process.returncode == 0

def apply_fixes():
    if not os.path.exists(LOG_FILE): return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f: log_data = f.read()

    fixes = 0
    file_regex = r"(\S+\.(?:c|cpp|h|hpp))"

    type_errs = re.findall(file_regex + r":\d+:\d+: error: unknown type name '([^']+)'", log_data)
    id_errs = re.findall(file_regex + r":\d+:\d+: error: use of undeclared identifier '([^']+)'", log_data)
    redef_errs = re.findall(file_regex + r":\d+:\d+: error: .*?redefinition.*?'(?:struct )?([a-zA-Z0-9_]+)'", log_data)
    sizeof_errs = re.findall(file_regex + r":\d+:\d+: error: invalid application of 'sizeof' to an incomplete type '([^']+)'", log_data)

    # FIX: Added LetterFloorTile to the core exclusion list
    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "ADPCM_STATE",
        "OSContPad", "OSContStatus", "Vtx", "Mtx", "ALHeap", "ALGlobals", "Gfx", "Acmd",
        "OS_NUM_EVENTS", "OSEvent", "Actor", "sChVegetable", "LetterFloorTile"
    }

    affected_files = set([e[0] for e in type_errs] + [e[0] for e in id_errs] + [e[0] for e in redef_errs] + [e[0] for e in sizeof_errs])

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue

        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # 0. Active Sanitization
        # FIX: Added LetterFloorTile here to actively clean up broken injections from previous runs
        for name in ["Actor", "sChVegetable", "LetterFloorTile"]:
            bad_struct = f"typedef struct {name} {name};\n"
            if bad_struct in content:
                content = content.replace(bad_struct, "")
                print(f"  [-] Sanitized incomplete type {name} in {os.path.basename(filepath)}")
                fixes += 1

        # 1. Advanced Redefinition Cleanup (FIXED GHOST INCREMENT BUG)
        file_redefs = [r[1] for r in redef_errs if r[0] == filepath]
        for name in file_redefs:
            if name in CORE_N64:
                old_c = content
                pattern_struct = rf"(typedef\s+(?:struct|union)\s*(?:[a-zA-Z0-9_]+\s*)?{{.*?}}\s*{name}\s*;)"
                content = re.sub(pattern_struct, r"/* \1 (Master Header Fix) */", content, flags=re.DOTALL)
                pattern_simple = rf"(typedef\s+[^;{{}}]+\s+{name}\s*;)"
                content = re.sub(pattern_simple, r"/* \1 (Master Header Fix) */", content)

                # ONLY increment if we actually modified the file!
                if content != old_c:
                    print(f"  [-] Resolved redefinition of {name} in {os.path.basename(filepath)}")
                    fixes += 1

        # 2. Foundation Injection
        all_file_errors = ([t[1] for t in type_errs if t[0] == filepath] + 
                           [i[1] for i in id_errs if i[0] == filepath] +
                           [s[1] for s in sizeof_errs if s[0] == filepath])

        if any(err in CORE_N64 for err in all_file_errors):
            if 'include "ultra/n64_types.h"' not in content:
                content = '#include "ultra/n64_types.h"\n' + content
                print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
                fixes += 1

        # 3a. Type Error Injection 
        type_and_sizeof = set([t[1] for t in type_errs if t[0] == filepath] + [s[1] for s in sizeof_errs if s[0] == filepath])
        for err in type_and_sizeof:
            if err in CORE_N64: continue
            decl = f"typedef struct {err} {err};\n"
            if decl not in content:
                content = decl + content
                print(f"  [+] Injected struct typedef: {err}")
                fixes += 1

        # 3b. Identifier Error Injection 
        file_identifiers = set([i[1] for i in id_errs if i[0] == filepath])
        for err in file_identifiers:
            if err in CORE_N64: continue
            if err.startswith(("D_", "sCh")):
                decl = f"extern u8 {err}[];\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected extern: {err}")
                    fixes += 1

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    if fixes == 0:
        print("\n⚠️ Checking for unhandled errors...")
        unhandled = re.findall(r"error: (.*)", log_data)
        if unhandled:
            print("\n🚨 UNHANDLED ERRORS DETECTED:")
            for err in list(dict.fromkeys(unhandled))[:10]: print(f"  - {err}")

    return fixes

def main():
    for i in range(1, 25):
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
