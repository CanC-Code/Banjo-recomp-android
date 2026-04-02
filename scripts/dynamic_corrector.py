import os
import re
import subprocess
import time

GRADLE_CMD = ["gradle", "-p", "Android", "assembleDebug", "--stacktrace"]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"

def harvest_macro(macro_name, sdk_dir="include"):
    """Crawls the N64 SDK headers to find and extract the missing macro definition."""
    for root, _, files in os.walk(sdk_dir):
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

def inject_macro_to_header(macro_block, macro_name, is_polyfill=False):
    if not os.path.exists(TYPES_HEADER): return False
    with open(TYPES_HEADER, "r") as f: content = f.read()
    
    if re.search(rf'^[ \t]*#[ \t]*define[ \t]+{macro_name}\b', content, re.MULTILINE): 
        return False

    pos = content.rfind('#endif')
    if pos != -1:
        label = "Auto-Polyfilled Missing Token" if is_polyfill else "Auto-Harvested SDK Macro"
        new_content = content[:pos] + f"\n/* {label}: {macro_name} */\n{macro_block}\n\n" + content[pos:]
        with open(TYPES_HEADER, "w") as f: f.write(new_content)
        return True
    return False

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
    close_errs = re.findall(file_regex + r":\d+:\d+: error: static declaration of 'close' follows non-static declaration", log_data)

    # Added OSYieldResult to the CORE_N64 list
    CORE_N64 = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64",
        "OSTask", "OSMesgQueue", "OSMesg", "OSTime", "OSThread", "ADPCM_STATE",
        "OSContPad", "OSContStatus", "Vtx", "Mtx", "ALHeap", "ALGlobals", "Gfx", "Acmd",
        "OS_NUM_EVENTS", "OSEvent", "Actor", "sChVegetable", 
        "POLEF_STATE", "RESAMPLE_STATE", "ENVMIX_STATE", "OSIntMask",
        "OSIoMesg", "OSPfs", "LookAt", "Light",
        "OSViMode", "OSTimer", "OSPiHandle", "OSDevMgr", "OSYieldResult"
    }

    all_identifiers = set([i[1] for i in id_errs])
    for err in all_identifiers:
        if err in CORE_N64: continue
        if err.isupper() or err.startswith(("G_", "OS_", "GU_", "RM_")):
            macro_block = harvest_macro(err)
            if macro_block:
                if inject_macro_to_header(macro_block, err, is_polyfill=False):
                    print(f"  [🤖] Auto-Harvested SDK Macro: {err}")
                    fixes += 1
                    id_errs = [e for e in id_errs if e[1] != err]
            else:
                dummy_block = f"#ifndef {err}\n#define {err} 0\n#endif"
                if inject_macro_to_header(dummy_block, err, is_polyfill=True):
                    print(f"  [🤖] Auto-Polyfilled Missing Token: {err}")
                    fixes += 1
                    id_errs = [e for e in id_errs if e[1] != err]

    affected_files = set(
        [e[0] for e in type_errs] + 
        [e[0] for e in id_errs] + 
        [e[0] for e in redef_errs] + 
        [e[0] for e in sizeof_errs] +
        [e for e in close_errs]
    )

    for filepath in affected_files:
        if not os.path.exists(filepath) or "/usr/include" in filepath: continue

        with open(filepath, "r") as f: content = f.read()
        original_content = content

        # Added OSYieldResult to sanitization list
        for name in ["Actor", "sChVegetable", "LetterFloorTile", "POLEF_STATE", "RESAMPLE_STATE", "ENVMIX_STATE", "OSIoMesg", "OSPfs", "LookAt", "OSViMode", "OSTimer", "OSPiHandle", "OSDevMgr", "OSYieldResult"]:
            bad_struct = f"typedef struct {name} {name};\n"
            if bad_struct in content:
                content = content.replace(bad_struct, "")
                print(f"  [-] Sanitized incomplete type {name} in {os.path.basename(filepath)}")
                fixes += 1

        if filepath in close_errs:
            if "bka_close" not in content:
                content = re.sub(r'\bclose\b', 'bka_close', content)
                print(f"  [-] Safely renamed internal 'close' to 'bka_close' natively in {os.path.basename(filepath)}")
                fixes += 1

        file_redefs = [r[1] for r in redef_errs if r[0] == filepath]
        for name in file_redefs:
            if name in CORE_N64:
                old_c = content
                pattern_struct = rf"(typedef\s+(?:struct|union)\s*(?:[a-zA-Z0-9_]+\s*)?\{{.*?\}}\s*{name}\s*;)"
                content = re.sub(pattern_struct, r"/* \1 (Master Header Fix) */", content, flags=re.DOTALL)
                pattern_simple = rf"(typedef\s+[^;{{}}]+\s+{name}\s*;)"
                content = re.sub(pattern_simple, r"/* \1 (Master Header Fix) */", content)
                if content != old_c:
                    print(f"  [-] Resolved redefinition of {name} in {os.path.basename(filepath)}")
                    fixes += 1

        all_file_errors = set([t[1] for t in type_errs if t[0] == filepath] + 
                              [i[1] for i in id_errs if i[0] == filepath] +
                              [s[1] for s in sizeof_errs if s[0] == filepath])

        handled_errors = set()

        for err in all_file_errors:
            pattern_struct = rf"(typedef\s+(?:struct|union)\s*(?:[a-zA-Z0-9_]+\s*)?\{{.*?\}}\s*{err}\s*;)"
            match = re.search(pattern_struct, content, re.DOTALL)
            if match:
                struct_def = match.group(1)
                content = content.replace(struct_def, "")
                include_idx = content.rfind('#include')
                if include_idx != -1:
                    eol = content.find('\n', include_idx) + 1
                    content = content[:eol] + "\n/* Auto-moved struct */\n" + struct_def + "\n" + content[eol:]
                else:
                    content = "/* Auto-moved struct */\n" + struct_def + "\n" + content
                print(f"  [-] Auto-moved real definition of {err} to the top of {os.path.basename(filepath)}")
                fixes += 1
                handled_errors.add(err)

        if any(err in CORE_N64 for err in all_file_errors):
            if 'include "ultra/n64_types.h"' not in content:
                content = '#include "ultra/n64_types.h"\n' + content
                print(f"  [+] Forced n64_types.h into {os.path.basename(filepath)}")
                fixes += 1
                handled_errors.update(CORE_N64.intersection(all_file_errors))

        type_and_sizeof = set([t[1] for t in type_errs if t[0] == filepath] + [s[1] for s in sizeof_errs if s[0] == filepath])
        for err in type_and_sizeof:
            if err in CORE_N64 or err in handled_errors: continue
            decl = f"typedef struct {err} {err};\n"
            if decl not in content:
                content = decl + content
                print(f"  [+] Injected struct typedef: {err}")
                fixes += 1

        file_identifiers = set([i[1] for i in id_errs if i[0] == filepath])
        for err in file_identifiers:
            if err in CORE_N64 or err in handled_errors: continue
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
