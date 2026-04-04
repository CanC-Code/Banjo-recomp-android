"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.

Cycle Enhancements:
  - Unlocked Build Loop: Removed hard aborts for libaudio and null float errors.
  - Condensed Error Summary: Generates a clean, path-stripped summary of unique errors
    when the loop halts, perfect for feeding into an LLM.
  - Synth Audio States: Automatically intercepts and stubs missing N64 audio states 
    (RESAMPLE_STATE, POLEF_STATE, ENVMIX_STATE).
  - Improved Anonymous Struct Parsing: FIX D now safely targets exact struct tags 
    to fix typedef redefinitions for structs like LetterFloorTile.
"""

import os
import re
import subprocess
import time
import sys

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug", 
    "--console=plain", "--max-workers=1", "--no-daemon", 
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError"
]
LOG_FILE = "Android/full_build_log.txt"
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE = "Android/app/src/main/cpp/ultra/n64_stubs.c"

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def run_build():
    print("\n🚀 Starting Build Cycle...")
    if not os.path.exists("Android"):
        os.makedirs("Android")
    with open(LOG_FILE, "w") as log:
        try:
            process = subprocess.Popen(
                GRADLE_CMD, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in process.stdout:
                clean_line = strip_ansi(line)
                log.write(clean_line)
                print(clean_line, end="")
            process.wait()
            return process.returncode == 0
        except Exception as e:
            print(f"🛑 Build execution failed: {e}")
            return False

def extract_incomplete_type(line):
    m = re.search(r"\(aka 'struct ([^']+)'\)", line)
    if m: return m.group(1)
    m = re.search(r"'struct ([^']+)'", line)
    if m: return m.group(1)
    m = re.search(r"'([^']+)'", line)
    if m: return m.group(1)
    return None

def source_path(path):
    if not path: return None
    p = path.replace("C/C++: ", "").strip()
    if "/Banjo-recomp-android/Banjo-recomp-android/" in p:
        return p.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
    return p

def generate_error_summary(log_data):
    """Strips file paths and duplicate spam to create a clean LLM prompt payload."""
    errors = set()
    for line in log_data.split('\n'):
        if "error:" in line and "too many errors emitted" not in line:
            # Strip everything up to "error: " to group identical errors across files
            clean_err = re.sub(r"^.*?:\d+:\d+:\s*error:\s*", "", line).strip()
            if clean_err:
                errors.add(clean_err)
    
    print("\n" + "="*60)
    print("📋 CONDENSED ERROR SUMMARY (Copy & Paste this to the LLM)")
    print("="*60)
    for e in sorted(errors):
        print(f"- {e}")
    print("="*60 + "\n")

def classify_errors(log_data):
    categories = {
        "missing_n64_types":  [],  
        "actor_pointer":      [],  
        "local_struct_fwd":   [],  
        "typedef_redef":      [],  
        "static_conflict":    [],  
        "incomplete_sizeof":  [],
        "undeclared_macros":  [], 
        "implicit_func":      [], 
        "undefined_symbols":  [],
        "audio_states":       [],
        "unknown":            [],
        "extraneous_brace":   False,
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"
    local_struct_map = {}

    for line in log_data.split('\n'):
        if "extraneous closing brace" in line:
            categories["extraneous_brace"] = True

        if "error:" not in line and "undefined reference" not in line and "undefined symbol" not in line:
            continue

        match = re.search(file_regex, line)
        filepath = source_path(match.group(1) if match else None)

        if filepath and ("/usr/" in filepath or "ndk" in filepath.lower()):
            filepath = None

        m_redef = re.search(r"typedef redefinition with different types \('([^']+)'(?:.*?)vs '([^']+)'(?:.*?)\)", line)
        m_static = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_ident = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_ref = re.search(r"undefined reference to `([^']+)'", line)
        m_undef_sym = re.search(r"undefined symbol: (.*)", line)
        
        m_sizeof = "invalid application of 'sizeof'" in line
        m_ptr = "arithmetic on a pointer to an incomplete type" in line
        m_array = "array has incomplete element type" in line
        m_def = "incomplete definition of type" in line

        if m_unknown and m_unknown.group(1) in ["RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE"]:
            categories["audio_states"].append(m_unknown.group(1))
        elif m_undef_ref:
            categories["undefined_symbols"].append(m_undef_ref.group(1).strip())
        elif m_undef_sym:
            sym = m_undef_sym.group(1).replace("'", "").strip()
            categories["undefined_symbols"].append(sym)
        elif m_implicit:
            categories["implicit_func"].append(m_implicit.group(1))
        elif m_ident:
            ident = m_ident.group(1)
            if ident == "actor" and filepath:
                categories["actor_pointer"].append(filepath)
            else:
                categories["undeclared_macros"].append(ident)
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

    # We now register audio states as global so they don't get locally forwarded
    known_global_types = {
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx", "RESAMPLE_STATE", "ENVMIX_STATE", "POLEF_STATE",
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
    if not os.path.exists(LOG_FILE): return 0
    with open(LOG_FILE, "r", encoding="utf-8") as f: log_data = f.read()

    categories = classify_errors(log_data)
    fixes = 0

    if categories["extraneous_brace"]:
        if os.path.exists(TYPES_HEADER):
            with open(TYPES_HEADER, "r") as f: content = f.read()
            original = content
            content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", content)
            content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", content)
            if content != original:
                with open(TYPES_HEADER, "w") as f: f.write(content)
                print(f"  [🛠️] Cleaned up syntax corruption in n64_types.h")
                fixes += 1

    # ── FIX 0: Header Protection ───────────────────────────────────────────
    if os.path.exists(TYPES_HEADER):
        with open(TYPES_HEADER, "r") as f: types_content = f.read()
        if "#pragma once" not in types_content:
            with open(TYPES_HEADER, "w") as f: f.write("#pragma once\n" + types_content)
            print("  [🛠️] Secured n64_types.h with #pragma once include guard")
            fixes += 1

    # ── FIX A: Priority inclusion of n64_types.h ─────────────────────────
    for filepath in set(categories["missing_n64_types"]):
        if not os.path.exists(filepath): continue
        if "/usr/include" in filepath or "ndk" in filepath or filepath.endswith("n64_types.h"): continue
        with open(filepath, "r") as f: content = f.read()
        if 'include "ultra/n64_types.h"' not in content:
            content = '#include "ultra/n64_types.h"\n' + content
            with open(filepath, "w") as f: f.write(content)
            print(f"  [🛠️] Injected n64_types.h include into {os.path.basename(filepath)}")
            fixes += 1

    # ── FIX B: 'actor' pointer injection ─────────────────────────────────
    for filepath in set(categories["actor_pointer"]):
        if not os.path.exists(filepath): continue
        with open(filepath, "r") as f: content = f.read()
        original = content
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'(\{)', r'\1\n    Actor *actor = (Actor *)this;', content, count=1)
            print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
        if content != original:
            with open(filepath, "w") as f: f.write(content)
            fixes += 1

    # ── FIX C: Local struct forward declaration injection ─────────────────
    if categories["local_struct_fwd"]:
        file_to_types = {}
        for filepath, type_name in categories["local_struct_fwd"]:
            file_to_types.setdefault(filepath, set()).add(type_name)

        for filepath, type_names in file_to_types.items():
            if not os.path.exists(filepath): continue
            with open(filepath, "r") as f: content = f.read()
            
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content: fwd_lines.append(fwd_decl)

            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n"
                with open(filepath, "w") as f: f.write(injection + content)
                print(f"  [🛠️] Injected forward decls {sorted(type_names)} into {os.path.basename(filepath)}")
                fixes += 1

    # ── FIX D: Typedef Redefinition (Resolving mismatched tags safely) ────────
    for filepath, type1, type2 in set(categories["typedef_redef"]):
        if not os.path.exists(filepath): continue
        with open(filepath, "r") as f: content = f.read()
        original = content
        
        t1_match = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
        t2_match = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
        
        tag1 = t1_match.group(1) if t1_match else None
        tag2 = t2_match.group(1) if t2_match else None

        if tag1 and tag2 and tag1 != tag2:
            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            old_tag = tag1 if target_tag == tag2 else tag2
            
            # Sub 1: Replace direct matching tags `struct old_tag` -> `struct target_tag`
            content, count1 = re.subn(rf"\bstruct\s+{re.escape(old_tag)}\b", f"struct {target_tag}", content)
            
            # Sub 2: If the struct was anonymous or formatted tightly `typedef struct {` 
            # and failed to map, try forcing the struct tag onto the anonymous typedef
            if count1 == 0:
                content, count2 = re.subn(r"typedef\s+struct\s*\{", f"typedef struct {target_tag} {{", content)
            
        if content != original:
            with open(filepath, "w") as f: f.write(content)
            print(f"  [🛠️] Harmonized typedef tags: '{old_tag}' -> '{target_tag}' in {os.path.basename(filepath)}")
            fixes += 1

    # ── FIX E: Incomplete SDK Types (sizeof traps) ────────────────────────
    if categories["incomplete_sizeof"]:
        if os.path.exists(TYPES_HEADER):
            with open(TYPES_HEADER, "r") as f: types_content = f.read()
            types_added = False
            for filepath, tag in set(categories["incomplete_sizeof"]):
                is_sdk = tag.isupper() or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_")) or (tag.endswith("_s") and tag[:-2].isupper())
                if is_sdk:
                    dummy_def = f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                    if f"struct {tag} {{" not in types_content:
                        types_content += dummy_def
                        types_added = True
                        print(f"  [🛠️] Injected dummy SDK struct '{tag}' into n64_types.h")
            if types_added:
                with open(TYPES_HEADER, "w") as f: f.write(types_content)
                fixes += 1

    # ── FIX F: Static Function Conflict (Resolving close() collision) ──────
    for filepath, func_name in set(categories["static_conflict"]):
        if not os.path.exists(filepath): continue
        with open(filepath, "r") as f: content = f.read()
        
        prefix = os.path.basename(filepath).split('.')[0]
        macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
        if macro_fix not in content:
            if '#include "ultra/n64_types.h"' in content:
                content = content.replace('#include "ultra/n64_types.h"', f'#include "ultra/n64_types.h"{macro_fix}')
            else:
                content = macro_fix + content
            with open(filepath, "w") as f: f.write(content)
            print(f"  [🛠️] Protected local function '{func_name}' via macro in {os.path.basename(filepath)}")
            fixes += 1

    # ── FIX G: Missing SDK Macros ────────────────────────
    if categories["undeclared_macros"] and os.path.exists(TYPES_HEADER):
        known_macros = {"ADPCMFSIZE": "9", "ADPCMVSIZE": "8"}
        with open(TYPES_HEADER, "r") as f: types_content = f.read()
        macros_added = False
        for macro in set(categories["undeclared_macros"]):
            if macro in known_macros:
                macro_def = f"\n#ifndef {macro}\n#define {macro} {known_macros[macro]}\n#endif\n"
                if f"#define {macro}" not in types_content:
                    types_content += macro_def
                    macros_added = True
                    print(f"  [🛠️] Injected missing SDK macro '{macro}' into n64_types.h")
        if macros_added:
            with open(TYPES_HEADER, "w") as f: f.write(types_content)
            fixes += 1

    # ── FIX H: Missing Standard C Libraries ────────────────────────
    if categories["implicit_func"] and os.path.exists(TYPES_HEADER):
        math_funcs = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        
        with open(TYPES_HEADER, "r") as f: types_content = f.read()
        includes_added = False
        for func in set(categories["implicit_func"]):
            header = None
            if func in math_funcs: header = "<math.h>"
            elif func in string_funcs: header = "<string.h>"
            elif func in stdlib_funcs: header = "<stdlib.h>"
            
            if header and f"#include {header}" not in types_content:
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
                print(f"  [🛠️] Injected {header} into n64_types.h to fix implicit '{func}'")
        if includes_added:
            with open(TYPES_HEADER, "w") as f: f.write(types_content)
            fixes += 1

    # ── FIX I: Auto-Generate Linker Stubs ──────────────────────────────
    if categories["undefined_symbols"]:
        stubs_added = False
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            with open(STUBS_FILE, "w") as f: f.write('#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                with open(cmake_file, "r") as f: cmake_content = f.read()
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace("add_library(", "add_library(\n        ultra/n64_stubs.c")
                    with open(cmake_file, "w") as f: f.write(cmake_content)

        with open(STUBS_FILE, "r") as f: existing_stubs = f.read()
            
        for sym in set(categories["undefined_symbols"]):
            if sym.startswith("_Z") or "vtable" in sym: continue
            stub_code = f"long long int {sym}() {{ return 0; }}\n"
            if f" {sym}(" not in existing_stubs:
                existing_stubs += stub_code
                stubs_added = True
                print(f"  [🛠️] Generated linker stub for missing N64 function '{sym}'")
                
        if stubs_added:
            with open(STUBS_FILE, "w") as f: f.write(existing_stubs)
            fixes += 1

    # ── FIX J: Audio / Synth Struct States ─────────────────────────────
    if categories["audio_states"] and os.path.exists(TYPES_HEADER):
        with open(TYPES_HEADER, "r") as f: types_content = f.read()
        audio_added = False
        for t in set(categories["audio_states"]):
            if f"typedef struct {t}" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            with open(TYPES_HEADER, "w") as f: f.write(types_content)
            print(f"  [🛠️] Injected missing N64 synth types into n64_types.h")
            fixes += 1

    if fixes == 0:
        generate_error_summary(log_data)

    return fixes

def main():
    for i in range(1, 100):
        print(f"\n{'='*40}\n--- Cycle {i} ---\n{'='*40}")
        if run_build():
            print("\n✅ Build Successful!")
            return

        result = apply_fixes()

        if result == 0:
            print("\n🛑 Loop halted. No fixable patterns found. Please review the Condensed Error Summary above.")
            break

        time.sleep(1)

if __name__ == "__main__":
    main()
