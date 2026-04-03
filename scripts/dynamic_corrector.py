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
    """
    categories = {
        "missing_n64_types":  [],  
        "actor_pointer":      [],  
        "local_struct_fwd":   [],  
        "libaudio_types":     [],  
        "null_float":         [],  
        "typedef_redef":      [],  
        "static_conflict":    [],  
        "incomplete_sizeof":  [],
        "unknown":            [],
    }

    libaudio_patterns = [
        r"libaudio\.h.*unknown type name 'Acmd'",
        r"libaudio\.h.*unknown type name 'ADPCM_STATE'",
    ]
    for pattern in libaudio_patterns:
        if re.search(pattern, log_data):
            categories["libaudio_types"].append(pattern)

    if re.search(r"initializing 'f32'.*incompatible type 'void \*'", log_data):
        categories["null_float"].append("NULL=(void*)0 assigned to f32 field")

    file_regex = r"(/[^:\s]+\.(?:c|cpp|h|cc|cxx)):"
    local_struct_map = {}

    def extract_incomplete_type(line):
        m = re.search(r"\(aka 'struct ([^']+)'\)", line)
        if m: return m.group(1)
        m = re.search(r"'struct ([^']+)'", line)
        if m: return m.group(1)
        m = re.search(r"'([^']+)'", line)
        if m: return m.group(1)
        return None

    for line in log_data.split('\n'):
        if "error:" not in line:
            continue

        match = re.search(file_regex, line)
        filepath = match.group(1) if match else None

        if filepath and ("/usr/" in filepath or "ndk" in filepath.lower()):
            filepath = None

        m_redef = re.search(r"typedef redefinition with different types \('([^']+)'(?:.*?)vs '([^']+)'(?:.*?)\)", line)
        m_static = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        
        m_sizeof = "invalid application of 'sizeof'" in line
        m_ptr = "arithmetic on a pointer to an incomplete type" in line
        m_array = "array has incomplete element type" in line
        m_def = "incomplete definition of type" in line

        if "unknown type name 'Acmd'" in line or "unknown type name 'ADPCM_STATE'" in line:
            pass  
        elif "initializing 'f32'" in line and "void *" in line:
            pass  
        elif "use of undeclared identifier 'actor'" in line and filepath:
            categories["actor_pointer"].append(filepath)
        elif m_redef and filepath:
            categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))
        elif m_static and filepath:
            categories["static_conflict"].append((filepath, m_static.group(1)))
        elif (m_sizeof or m_ptr or m_array or m_def) and filepath:
            inc_type = extract_incomplete_type(line)
            if inc_type:
                categories["incomplete_sizeof"].append((filepath, inc_type))
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
        if "/usr/include" in filepath or "ndk" in filepath or filepath.endswith("n64_types.h"):
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
        for filepath, type1, type2 in set(categories["typedef_redef"]):
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            original = content
            
            t1_match = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_match = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            
            tag1 = t1_match.group(1) if t1_match else None
            tag2 = t2_match.group(1) if t2_match else None

            # [FIX APPLIED]: Handle named struct mismatches (e.g. 'chVegetable_s' vs 'ch_vegatable')
            if tag1 and tag2 and tag1 != tag2:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "/* AUTO: forward declarations */" in line:
                        for j in range(i + 1, min(i + 20, len(lines))):
                            if f"struct {tag1}" in lines[j] and "typedef" in lines[j]:
                                lines[j] = lines[j].replace(f"struct {tag1}", f"struct {tag2}")
                            elif f"struct {tag2}" in lines[j] and "typedef" in lines[j]:
                                lines[j] = lines[j].replace(f"struct {tag2}", f"struct {tag1}")
                        break
                content = '\n'.join(lines)
            
            # Fallback for anonymous structs
            elif tag1 or tag2:
                tag = tag1 or tag2
                lines = content.split('\n')
                for i, l in enumerate(lines):
                    if re.search(r"\}\s*" + tag + r"\s*;", l):
                        for j in range(i, -1, -1):
                            if "typedef struct" in lines[j]:
                                if "{" in lines[j]:
                                    lines[j] = re.sub(r"typedef\s+struct\s*\{", f"typedef struct {tag} {{", lines[j])
                                else:
                                    lines[j] = re.sub(r"typedef\s+struct", f"typedef struct {tag}", lines[j])
                                break
                content = '\n'.join(lines)
                
            if content != original:
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"  [🛠️] Harmonized typedef tags in {os.path.basename(filepath)}")
                fixes += 1

    # ── FIX E: Incomplete SDK Types (sizeof traps) ────────────────────────
    if categories["incomplete_sizeof"]:
        if os.path.exists(TYPES_HEADER):
            with open(TYPES_HEADER, "r") as f:
                types_content = f.read()
            
            types_added = False
            for filepath, tag in set(categories["incomplete_sizeof"]):
                if tag.isupper() or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_")):
                    dummy_def = f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                    if f"struct {tag} {{" not in types_content:
                        types_content += dummy_def
                        types_added = True
                        print(f"  [🛠️] Injected dummy SDK struct '{tag}' into n64_types.h")
            
            if types_added:
                with open(TYPES_HEADER, "w") as f:
                    f.write(types_content)
                fixes += 1

    # ── FIX F: Static Function Conflict (Resolving close() collision) ──────
    if categories["static_conflict"]:
        for filepath, func_name in set(categories["static_conflict"]):
            if not os.path.exists(filepath):
                continue
            with open(filepath, "r") as f:
                content = f.read()
            original = content
            
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
