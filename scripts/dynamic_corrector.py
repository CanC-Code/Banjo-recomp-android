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
        "missing_n64_types":  [],  # file needs n64_types.h include
        "actor_pointer":      [],  # 'actor' undeclared in a TU
        "local_struct_fwd":   [],  # unknown type name for a local struct
        "libaudio_types":     [],  # Acmd / ADPCM_STATE missing (header-level)
        "null_float":         [],  # NULL assigned to f32 (header-level)
        "unknown":            [],
    }

    # ── Header-level traps ────────────────────────────────────────────────
    # These originate inside shared headers, not individual TUs.
    # Looping cannot fix them; they require n64_types.h changes.
    libaudio_patterns = [
        r"libaudio\.h.*unknown type name 'Acmd'",
        r"libaudio\.h.*unknown type name 'ADPCM_STATE'",
    ]
    for pattern in libaudio_patterns:
        if re.search(pattern, log_data):
            categories["libaudio_types"].append(pattern)

    # NULL → f32 errors come from stddef.h redefining NULL as (void*)0
    # after n64_types.h; the fix is in n64_types.h, not per-TU.
    if re.search(r"initializing 'f32'.*incompatible type 'void \*'", log_data):
        categories["null_float"].append("NULL=(void*)0 assigned to f32 field")

    # ── Per-file error parsing ─────────────────────────────────────────────
    file_regex = r"(/[^:\s]+\.(?:c|cpp|h|cc|cxx)):"
    # Map filepath → set of unknown type names from that file
    local_struct_map = {}

    for line in log_data.split('\n'):
        if "error:" not in line:
            continue

        match = re.search(file_regex, line)
        filepath = match.group(1) if match else None

        # Skip NDK/sysroot headers — we can't patch those
        if filepath and ("/usr/" in filepath or "ndk" in filepath.lower()):
            filepath = None

        if "unknown type name 'Acmd'" in line or "unknown type name 'ADPCM_STATE'" in line:
            pass  # already captured at header level

        elif "initializing 'f32'" in line and "void *" in line:
            pass  # already captured at header level

        elif "use of undeclared identifier 'actor'" in line and filepath:
            categories["actor_pointer"].append(filepath)

        else:
            m = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
            if m:
                type_name = m.group(1)
                if filepath:
                    local_struct_map.setdefault(filepath, set()).add(type_name)
                else:
                    categories["unknown"].append(line.strip())
            elif filepath and os.path.exists(filepath):
                categories["missing_n64_types"].append(filepath)
            elif line.strip():
                categories["unknown"].append(line.strip())

    # Resolve local_struct_map into actionable entries.
    known_global_types = {
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx",
        "OSContPad", "OSTimer", "OSTime", "OSMesg", "OSEvent",
        "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
        "Actor", "ActorMarker",
        # scalars
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

    # ── HALT: header-level libaudio type errors ───────────────────────────
    if categories["libaudio_types"]:
        print("\n🛑 HEADER-LEVEL ERRORS in libaudio.h:")
        print("   → unknown type name 'Acmd' and/or 'ADPCM_STATE'")
        print("   Fix required in n64_types.h: add stubs before #include <PR/libaudio.h>")
        return -1

    # ── HALT: NULL→f32 errors (header-level) ─────────────────────────────
    if categories["null_float"]:
        print("\n🛑 HEADER-LEVEL ERROR: NULL=(void*)0 assigned to f32 fields.")
        print("   Fix required in n64_types.h: redefine NULL to 0 before system includes.")
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
        # Group by file
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
                # Derive tag: strip leading 's'/'S' prefix for tag name
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                
                # Build the complete typedef string
                fwd_decl = f"typedef struct {tag}_s {t};"
                
                # [FIX APPLIED]: Simply check if this exact declaration is missing from the file
                if fwd_decl not in content:
                    fwd_lines.append(fwd_decl)

            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + \
                            "\n".join(fwd_lines) + "\n"
                content = injection + content
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"  [🛠️] Injected forward decls {sorted(type_names)} into "
                      f"{os.path.basename(filepath)}")
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
