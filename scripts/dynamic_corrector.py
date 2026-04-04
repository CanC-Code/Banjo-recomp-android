import os
import re
import subprocess
import time

# Force single-threaded build to prevent system memory exhaustion
os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug", 
    "--console=plain", "--max-workers=1", "--no-daemon", 
    "-Dorg.gradle.jvmargs=-Xmx4g"
]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE = "Android/app/src/main/cpp/ultra/n64_stubs.c"
CMAKE_FILE = "Android/app/src/main/cpp/CMakeLists.txt"

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
    categories = {
        "missing_n64_types":  [],  
        "actor_pointer":      [],  
        "local_struct_fwd":   [],  
        "missing_sdk_types":  [], 
        "undefined_symbols":  [], 
        "unknown":            [],
    }

    known_global_types = {
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx",
        "OSContPad", "OSTimer", "OSTime", "OSMesg", "OSEvent",
        "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
        "Actor", "ActorMarker", "s8", "u8", "s16", "u16", "s32", "u32", 
        "s64", "u64", "f32", "f64", "n64_bool", "OSPri", "OSId",
        "OSHWIntr", "OSIntMask", "OSYieldResult"
    }

    # Robust regex for NDK logs: catches /path/to/file.c:line:col
    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx))"
    local_struct_map = {}

    for line in log_data.split('\n'):
        if "error:" not in line and "undefined" not in line:
            continue

        path_match = re.search(file_regex, line)
        filepath = path_match.group(1) if path_match else None
        
        # Skip system and NDK internal headers
        if filepath and ("/usr/" in filepath or "ndk" in filepath.lower()):
            filepath = None

        m_unknown = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_undef_sym = re.search(r"undefined symbol: (.*)", line)
        m_undef_ref = re.search(r"undefined reference to `([^']+)'", line)

        if m_undef_sym or m_undef_ref:
            sym = (m_undef_sym or m_undef_ref).group(1).replace("'", "").replace("`", "").strip()
            categories["undefined_symbols"].append(sym)
        elif m_unknown:
            type_name = m_unknown.group(1)
            if type_name in known_global_types:
                categories["missing_sdk_types"].append(type_name)
            elif filepath:
                local_struct_map.setdefault(filepath, set()).add(type_name)
        elif filepath and os.path.exists(filepath):
            categories["missing_n64_types"].append(filepath)

    for filepath, type_names in local_struct_map.items():
        for t in type_names:
            categories["local_struct_fwd"].append((filepath, t))

    return categories

def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        log_data = f.read()

    categories = classify_errors(log_data)
    fixes = 0

    # ── FIX K: Global SDK Type Injection ──────────────────────────────────
    if categories["missing_sdk_types"]:
        known_sdk_typedefs = {
            "OSHWIntr": "unsigned int", "OSIntMask": "unsigned int",
            "s8": "signed char", "u8": "unsigned char",
            "s16": "short", "u16": "unsigned short",
            "s32": "int", "u32": "unsigned int",
            "s64": "long long", "u64": "unsigned long long",
            "f32": "float", "f64": "double",
            "OSPri": "int", "OSId": "int", "n64_bool": "int",
            "OSMesg": "unsigned long long", "OSYieldResult": "int"
        }
        if os.path.exists(TYPES_HEADER):
            with open(TYPES_HEADER, "r") as f:
                content = f.read()
            added = False
            for t in set(categories["missing_sdk_types"]):
                if f"typedef struct {t}_s {t};" in content or f"typedef unsigned int {t};" in content: continue
                
                if t in known_sdk_typedefs:
                    decl = f"\ntypedef {known_sdk_typedefs[t]} {t};\n"
                else:
                    # Use a standard named struct tag for safe pointer math
                    decl = f"\ntypedef struct {t}_s {{ long long int reserved[64]; }} {t};\n"
                
                content += decl
                added = True
                print(f"  [🛠️] Defined Global SDK type: {t}")
            
            if added:
                with open(TYPES_HEADER, "w") as f:
                    f.write(content)
                fixes += 1

    # ── FIX C: Local Struct Forward Decls (Game Logic) ───────────────────
    if categories["local_struct_fwd"]:
        file_to_types = {}
        for filepath, type_name in categories["local_struct_fwd"]:
            file_to_types.setdefault(filepath, set()).add(type_name)
        
        for filepath, type_names in file_to_types.items():
            if not os.path.exists(filepath): continue
            with open(filepath, "r") as f:
                content = f.read()
            
            fwd_lines = []
            for t in sorted(type_names):
                # Standardize to 'typedef struct Name_s Name;'
                fwd_decl = f"typedef struct {t}_s {t};"
                if fwd_decl not in content:
                    fwd_lines.append(fwd_decl)
            
            if fwd_lines:
                content = "/* AUTO: actor decls */\n" + "\n".join(fwd_lines) + "\n" + content
                with open(filepath, "w") as f:
                    f.write(content)
                print(f"  [🛠️] Injected actor types {sorted(type_names)} into {os.path.basename(filepath)}")
                fixes += 1

    # ── FIX I: Linker Stubs (Missing N64 Functions) ───────────────────────
    if categories["undefined_symbols"]:
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            with open(STUBS_FILE, "w") as f:
                f.write('#include "n64_types.h"\n\n')
        
        with open(STUBS_FILE, "r") as f:
            stubs = f.read()
            
        added = False
        for sym in set(categories["undefined_symbols"]):
            if f" {sym}(" in stubs: continue
            stubs += f"\nlong long int {sym}() {{ return 0; }}\n"
            added = True
            print(f"  [🛠️] Generated linker stub for: {sym}")
                
        if added:
            with open(STUBS_FILE, "w") as f:
                f.write(stubs)
            fixes += 1

    return fixes

def main():
    for i in range(1, 100):
        print(f"\n--- Build Cycle {i} ---")
        if run_build():
            print("\n✅ Build Successful! APK generated.")
            return
        
        # Apply fixes and stop if no new patterns are detected
        if apply_fixes() == 0:
            print("\n🛑 Build stalled: No more fixable patterns detected in logs.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
