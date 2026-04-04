import os
import re
import subprocess
import time

# Force Ninja and CMake to run single-threaded to prevent system OOM
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
        "libaudio_types":     [],  
        "null_float":         [],  
        "typedef_redef":      [],  
        "static_conflict":    [],  
        "incomplete_sizeof":  [],
        "undeclared_macros":  [], 
        "implicit_func":      [], 
        "undefined_symbols":  [], 
        "missing_sdk_types":  [], 
        "unknown":            [],
    }

    known_global_types = {
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx",
        "OSContPad", "OSTimer", "OSTime", "OSMesg", "OSEvent",
        "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
        "Actor", "ActorMarker",
        "s8", "u8", "s16", "u16", "s32", "u32", "s64", "u64",
        "f32", "f64", "n64_bool", "OSPri", "OSId",
        "OSHWIntr", "OSIntMask", "OSYieldResult"
    }

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
        if "error:" not in line and "undefined reference" not in line and "undefined symbol" not in line:
            continue

        match = re.search(file_regex, line)
        filepath = match.group(1) if match else None

        m_unknown = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_implicit = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_sym = re.search(r"undefined symbol: (.*)", line)
        m_inc = "incomplete type" in line 

        if m_undef_sym:
            sym = m_undef_sym.group(1).replace("'", "").strip()
            categories["undefined_symbols"].append(sym)
        elif m_implicit:
            categories["implicit_func"].append(m_implicit.group(1))
        elif m_unknown:
            type_name = m_unknown.group(1)
            if type_name in known_global_types:
                categories["missing_sdk_types"].append(type_name)
            elif filepath:
                local_struct_map.setdefault(filepath, set()).add(type_name)
        elif m_inc and filepath:
            inc_type = extract_incomplete_type(line)
            if inc_type:
                categories["incomplete_sizeof"].append((filepath, inc_type))
        elif filepath and os.path.exists(filepath):
            categories["missing_n64_types"].append(filepath)

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

    # ── FIX K: Overhauled SDK Type Injection ──────────────────────────────
    if categories["missing_sdk_types"]:
        known_sdk_typedefs = {
            "OSHWIntr": "unsigned int",
            "OSIntMask": "unsigned int",
            "s8": "signed char", "u8": "unsigned char",
            "s16": "short", "u16": "unsigned short",
            "s32": "int", "u32": "unsigned int",
            "s64": "long long", "u64": "unsigned long long",
            "f32": "float", "f64": "double",
            "OSPri": "int", "OSId": "int", "n64_bool": "int",
            "OSMesg": "unsigned long long", # FIX: Use long long to handle both ints and pointers
            "OSYieldResult": "int"
        }
        
        if os.path.exists(TYPES_HEADER):
            with open(TYPES_HEADER, "r") as f:
                content = f.read()
            
            added = False
            for t in set(categories["missing_sdk_types"]):
                if f" {t};" in content: continue
                
                if t in known_sdk_typedefs:
                    decl = f"\ntypedef {known_sdk_typedefs[t]} {t};\n"
                else:
                    decl = f"\ntypedef struct {{ long long int reserved[64]; }} {t};\n"
                
                content += decl
                added = True
                print(f"  [🛠️] Defined missing SDK type: {t}")
            
            if added:
                with open(TYPES_HEADER, "w") as f:
                    f.write(content)
                fixes += 1

    # ── FIX I: Auto-Linker Stubs ──────────────────────────────────────────
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
            stubs += f"long long int {sym}() {{ return 0; }}\n"
            added = True
            print(f"  [🛠️] Stubbed missing function: {sym}")
                
        if added:
            with open(STUBS_FILE, "w") as f:
                f.write(stubs)
            fixes += 1

    return fixes

def main():
    for i in range(1, 50):
        print(f"\n--- Build Cycle {i} ---")
        if run_build():
            print("\n✅ Success! APK built.")
            return
        if apply_fixes() == 0:
            print("\n🛑 No more automatic fixes possible.")
            break
        time.sleep(1)

if __name__ == "__main__":
    main()
