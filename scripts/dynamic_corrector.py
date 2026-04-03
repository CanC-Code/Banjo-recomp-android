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
    Values are lists of (filepath, extra_context) tuples where relevant.
    """
    categories = {
        "missing_n64_types":  [],  
        "actor_pointer":      [],  
        "local_struct_fwd":   [],  
        "libaudio_types":     [],  
        "null_float":         [],  
        "typedef_redef":      [],  # tuples of (filepath, actual_tag, injected_tag)
        "static_conflict":    [],  # tuples of (filepath, func_name)
        "unknown":            [],
    }

    # ── Header-level traps ────────────────────────────────────────────────
    libaudio_patterns = [
        r"libaudio\.h.*unknown type name 'Acmd'",
        r"libaudio\.h.*unknown type name 'ADPCM_STATE'",
    ]
    for pattern in libaudio_patterns:
        if re.search(pattern, log_data):
            categories["libaudio_types"].append(pattern)

    if re.search(r"initializing 'f32'.*incompatible type 'void \*'", log_data):
        categories["null_float"].append("NULL=(void*)0 assigned to f32 field")

    # ── Per-file error parsing ─────────────────────────────────────────────
    file_regex = r"(/[^:\s]+\.(?:c|cpp|h|cc|cxx)):"
    local_struct_map = {}

    for line in log_data.split('\n'):
        if "error:" not in line:
            continue

        match = re.search(file_regex, line)
        filepath = match.group(1) if match else None

        # Skip NDK/sysroot headers
        if filepath and ("/usr/" in filepath or "ndk" in filepath.lower()):
            filepath = None

        m_redef = re.search(r"typedef redefinition with different types \('struct ([^']+)' vs 'struct ([^']+)'\)", line)
        m_static = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)

        if "unknown type name 'Acmd'" in line or "unknown type name 'ADPCM_STATE'" in line:
            pass  
        elif "initializing 'f32'" in line and "void *" in line:
            pass  
        elif "use of undeclared identifier 'actor'" in line and filepath:
            categories["actor_pointer"].append(filepath)
        elif m_redef:
            if filepath:
                categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))
        elif m_static:
            if filepath:
                categories["static_conflict"].append((filepath, m_static.group(1)))
        elif m_unknown:
            type_name = m_unknown.group(1)
            if filepath:
                local_struct_map.setdefault(filepath, set()).add(type_name)
            else:
                categories["unknown"].append(line.strip())
        elif filepath and os.path.exists(filepath):
            categories["missing_n64_types"].append(filepath)
        else:
            if line.strip():
                categories["unknown"].append(line.strip())

    # Resolve local_struct_map
    known_global_types = {
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx",
        "OSContPad", "OSTimer", "OSTime", "OSMesg", "OSEvent",
        "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
        "Actor", "ActorMarker",
        "s8", "u8", "s16", "u16", "s32", "u32", "s64", "u64",
        "f32", "f64", "n64_bool", "OSPri", "OSId",
    }
    for filepath, type_names in local_struct_map.items():
        for t in type_names:
            if t not in known_global_types:
                categories["local_struct_fwd"].append((filepath, t))

    return categories

def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_data = f.read()

    categories = classify_errors(log_data)
    fixes = 0

    if categories["libaudio_types"]:
        print("\n🛑 HEADER-LEVEL ERRORS in libaudio.h:")
        return -1

    if categories["null_float"]:
        print("\n🛑 HEADER-LEVEL ERROR: NULL=(void*)0 assigned to f32 fields.")
        return -1

    # ── FIX A: Priority inclusion of n64_types.h ─────────────────────────
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

    # ── FIX B: 'actor' pointer injection ─────────────────────────────────
    if categories["actor_pointer"]:
        for filepath in set(categories["actor_pointer"]):
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            original = content
            if "Actor *actor =" not in content and "this" in content:
                content = re.sub(
                    r'(\{)',
                    r'\1\n    Actor *actor = (Actor *)this;',
                    content, count=1
                )
                print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
            if content != original:
                with open(filepath, "w") as f:
                    f.write(content)
                fixes += 1

    # ── FIX C: Local struct forward declaration injection ─────────────────
    if categories["local_struct_fwd"]:
        file_to_types = {}
        for filepath, type_name in categories["local_struct_fwd"]:
            file_to_types.setdefault(filepath, set()).add(type_name)

        for filepath, type_names in file_to_types.items():
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content:
                    fwd_lines.append(fwd_decl)

            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + \
                            "\n".join(fwd_lines) + "\n"
                content = injection + content
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"  [🛠️] Injected forward decls {sorted(type_names)} into {os.path.basename(filepath)}")
                fixes += 1

    # ── FIX D: Typedef Redefinition (Resolving mismatched tags) ───────────
    if categories["typedef_redef"]:
        for filepath, actual_tag, injected_tag in set(categories["typedef_redef"]):
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            original = content
            
            # Rewrite the incorrect injected tag to match the actual tag found in the file
            if "anonymous" in actual_tag:
                content = content.replace("typedef struct {", f"typedef struct {injected_tag} {{", 1)
            else:
                content = content.replace(f"struct {injected_tag} ", f"struct {actual_tag} ")
                content = content.replace(f"struct {injected_tag};", f"struct {actual_tag};")
                
            if content != original:
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"  [🛠️] Harmonized typedef tag from {injected_tag} to {actual_tag} in {os.path.basename(filepath)}")
                fixes += 1

    # ── FIX E: Static Function Conflict (Resolving close() collision) ──────
    if categories["static_conflict"]:
        for filepath, func_name in set(categories["static_conflict"]):
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            original = content
            
            # Use preprocessor macro to safely rename the function locally without breaking code
            macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{func_name}\n"
            if macro_fix not in content:
                if '#include "ultra/n64_types.h"' in content:
                    content = content.replace('#include "ultra/n64_types.h"', f'#include "ultra/n64_types.h"{macro_fix}')
                else:
                    content = macro_fix + content
                
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"  [🛠️] Protected local function '{func_name}' via macro in {os.path.basename(filepath)}")
                fixes += 1

    # ── UNKNOWN errors: report but don't fix ─────────────────────────────
    if categories["unknown"] and fixes == 0:
        print("\n⚠️  Unrecognized errors (no automatic fix available):")
        for msg in list(dict.fromkeys(categories["unknown"]))[:10]:
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
            print("\n🛑 Loop halted. Manual fix required in n64_types.h.")
            break
        elif result == 0:
            print("\n🛑 Loop halted. No fixable patterns found.")
            break

        time.sleep(1)

if __name__ == "__main__":
    main()
