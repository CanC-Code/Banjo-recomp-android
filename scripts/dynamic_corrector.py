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
    
    # 🆕 Detect bad typedefs created by previous runs
    unexpected_type_errs = re.findall(file_regex + r":\d+:\d+: error: unexpected type name '([^']+)': expected expression", log_data)
    incomplete_errs = re.findall(file_regex + r":\d+:\d+: error: variable has incomplete type '([^']+)'", log_data)

    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "ADPCM_STATE",
        "OSContPad", "OSContStatus", "Vtx", "Mtx", "ALHeap", "ALGlobals", "Gfx", "Acmd",
        "OSEvent", "OS_NUM_EVENTS"
    }

    affected_files = set([e[0] for e in type_errs] + [e[0] for e in id_errs] + [e[0] for e in redef_errs] + [e[0] for e in unexpected_type_errs] + [e[0] for e in incomplete_errs])

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue
        
        with open(filepath, "r") as f: content = f.read()
        original_content = content
        
        # 0. Clean up mistaken script injections
        file_unexpected = [u[1] for u in unexpected_type_errs if u[0] == filepath]
        file_incomplete = [i[1] for i in incomplete_errs if i[0] == filepath]
        for name in file_unexpected + file_incomplete:
            # Strip the exact 'typedef struct X X;' that the script injected previously
            pattern_bad_struct = rf"(typedef\s+struct\s+{name}\s+{name}\s*;)"
            if re.search(pattern_bad_struct, content):
                content = re.sub(pattern_bad_struct, rf"/* Removed bad typedef: {name} */", content)
                print(f"  [-] Scrubbed incorrect struct typedef for {name} in {os.path.basename(filepath)}")
                fixes += 1
        
        # 1. Advanced Redefinition Cleanup
        file_redefs = [r[1] for r in redef_errs if r[0] == filepath]
        for name in file_redefs:
            if name in CORE_N64:
                pattern_struct = rf"(typedef\s+(?:struct|union)\s*(?:[a-zA-Z0-9_]+\s*)?{{.*?}}\s*{name}\s*;)"
                content = re.sub(pattern_struct, r"/* \1 (Master Header Fix) */", content, flags=re.DOTALL)
                pattern_simple = rf"(typedef\s+[^;{{}}]+\s+{name}\s*;)"
                content = re.sub(pattern_simple, r"/* \1 (Master Header Fix) */", content)
                print(f"  [-] Resolved redefinition of {name} in {os.path.basename(filepath)}")
                fixes += 1

        # 2. Foundation Injection
        file_errors = [t[1] for t in type_errs if t[0] == filepath] + [i[1] for i in id_errs if i[0] == filepath] + file_unexpected + file_incomplete
        if any(err in CORE_N64 for err in file_errors):
            if 'include "ultra/n64_types.h"' not in content:
                content = '#include "ultra/n64_types.h"\n' + content
                print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
                fixes += 1

        # 3. Extern and Struct Injection
        for err in set([t[1] for t in type_errs if t[0] == filepath] + [i[1] for i in id_errs if i[0] == filepath]):
            if err.startswith(("D_", "sCh")):
                decl = f"extern u8 {err}[];\n"
                if decl not in content:
                    content = decl + content
                    print(f"  [+] Injected extern: {err}")
                    fixes += 1
            # Prevent uppercase macros/constants from being turned into structs
            elif err not in CORE_N64 and not err.startswith(("D_", "sCh")):
                if not re.match(r"^[A-Z0-9_]+$", err):
                    decl = f"typedef struct {err} {err};\n"
                    if decl not in content:
                        content = decl + content
                        print(f"  [+] Injected struct typedef: {err}")
                        fixes += 1
                else:
                    # Dummy macro for all-caps identifiers to prevent zero-length arrays or logic breaks
                    decl = f"#ifndef {err}\n#define {err} 1\n#endif\n"
                    if decl not in content:
                        content = decl + content
                        print(f"  [+] Injected dummy macro: {err}")
                        fixes += 1

        if content != original_content:
            with open(filepath, "w") as f: f.write(content)

    return fixes

def main():
    for i in range(1, 20):
        print(f"\n--- Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful!")
            return
        if apply_fixes() == 0:
            print("\n🛑 No more fixable patterns found. Check the full_build_log.txt for UNHANDLED errors.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
