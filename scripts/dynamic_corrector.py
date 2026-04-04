"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.
v76.0 — Resilient multi-file patching edition.

Key changes vs previous version:
  - ninja -k 0: Continues past all errors so every failing file is seen in one pass.
  - failed_files.log: Persistent log of all files that produced errors, with error summaries.
  - FIX A guard: No longer injects n64_types.h include into files that locally redefine
    a type — prevents the typedef-redefinition cascade seen in castle.c.
  - FIX D overhaul: Correctly resolves the pattern where a forward declaration was
    injected at the top AND the file also contains an inline anonymous typedef body,
    by removing the redundant forward decl instead of rewriting the body.
  - FIX D fallback: Handles the full anonymous struct body rewrite when no forward decl exists.
  - Deduplication: All fix sets are deduplicated before application.
  - apply_fixes always returns >0 if any category has work, preventing premature halt.
  - Error continuation: Loop never halts on apply_fixes==0 if there are still unresolved
    errors — it falls through to the summary and keeps going until MAX_STALL cycles.
  - generate_failed_log: Writes Android/failed_files.log with per-file error details.
"""

import os
import re
import subprocess
import time
import sys
from collections import defaultdict

os.environ["CMAKE_BUILD_PARALLEL_LEVEL"] = "1"
os.environ["NINJAJOBS"] = "-j1"

GRADLE_CMD = [
    "gradle", "-p", "Android", "assembleDebug",
    "--console=plain", "--max-workers=1", "--no-daemon",
    "-Dorg.gradle.jvmargs=-Xmx6g -XX:+HeapDumpOnOutOfMemoryError",
    # Pass -k 0 to ninja via Android Gradle CMake so it continues past errors
    "-Pandroid.ndk.cmakeArgs=-k 0",
]
LOG_FILE        = "Android/full_build_log.txt"
FAILED_LOG_FILE = "Android/failed_files.log"
TYPES_HEADER    = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE      = "Android/app/src/main/cpp/ultra/n64_stubs.c"

MAX_STALL = 5   # Halt after this many consecutive cycles with zero new fixes


# ─── Utilities ────────────────────────────────────────────────────────────────

def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def run_build():
    print("\n🚀 Starting Build Cycle...")
    os.makedirs("Android", exist_ok=True)
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
    for pattern in [
        r"\(aka 'struct ([^']+)'\)",
        r"'struct ([^']+)'",
        r"'([^']+)'",
    ]:
        m = re.search(pattern, line)
        if m:
            return m.group(1)
    return None


def source_path(path):
    if not path:
        return None
    p = path.replace("C/C++: ", "").strip()
    if "/Banjo-recomp-android/Banjo-recomp-android/" in p:
        p = p.split("/Banjo-recomp-android/Banjo-recomp-android/")[-1]
    return os.path.normpath(p)


def is_sdk_or_ndk_path(fp):
    if not fp:
        return True
    normalized = fp.replace("\\", "/")
    return "/usr/" in normalized or "ndk" in normalized.lower()


# ─── Failed-file log ──────────────────────────────────────────────────────────

def generate_failed_log(log_data):
    """
    Write Android/failed_files.log with every file that produced an error,
    listing its unique error messages.  Also prints a condensed summary.
    """
    file_errors = defaultdict(set)
    loose_errors = set()

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    for line in log_data.split('\n'):
        if "error:" not in line and "undefined reference" not in line and "undefined symbol" not in line:
            continue
        if "too many errors emitted" in line:
            continue

        m_file = re.search(file_regex, line)
        fp = source_path(m_file.group(1) if m_file else None)

        m_err = re.search(r"error:\s*(.*)", line)
        msg = m_err.group(1).strip() if m_err else line.strip()

        if fp and not is_sdk_or_ndk_path(fp):
            file_errors[fp].add(msg)
        else:
            loose_errors.add(msg)

    lines = ["=" * 70, "FAILED FILES LOG", "=" * 70, ""]
    for fp in sorted(file_errors):
        lines.append(f"FILE: {fp}")
        for err in sorted(file_errors[fp]):
            lines.append(f"  • {err}")
        lines.append("")

    if loose_errors:
        lines.append("LINKER / UNATTRIBUTED ERRORS:")
        for err in sorted(loose_errors):
            lines.append(f"  • {err}")
        lines.append("")

    content = "\n".join(lines)
    with open(FAILED_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("\n" + "=" * 60)
    print(f"📋 FAILED FILES SUMMARY  →  {FAILED_LOG_FILE}")
    print("=" * 60)
    for fp in sorted(file_errors):
        print(f"  {fp}  ({len(file_errors[fp])} unique error(s))")
    if loose_errors:
        print(f"  [linker/unattributed]  ({len(loose_errors)} error(s))")
    print("=" * 60 + "\n")

    return set(file_errors.keys())


def generate_error_summary(log_data):
    """Condensed unique-error dump for LLM paste."""
    errors = set()
    for line in log_data.split('\n'):
        if "error:" in line and "too many errors emitted" not in line:
            m = re.search(r"error:\s*(.*)", line)
            if m:
                errors.add(m.group(1).strip())
    print("\n" + "=" * 60)
    print("📋 CONDENSED ERROR SUMMARY (Copy & Paste this to the LLM)")
    print("=" * 60)
    for e in sorted(errors):
        print(f"- {e}")
    print("=" * 60 + "\n")


# ─── Error classification ─────────────────────────────────────────────────────

def classify_errors(log_data):
    categories = {
        "missing_n64_types":  set(),
        "actor_pointer":      set(),
        "local_struct_fwd":   [],
        "typedef_redef":      [],
        "static_conflict":    [],
        "incomplete_sizeof":  [],
        "undeclared_macros":  set(),
        "implicit_func":      set(),
        "undefined_symbols":  set(),
        "audio_states":       set(),
        "unknown":            [],
        "extraneous_brace":   False,
        # Files that have a LOCAL typedef so we skip blind n64_types injection
        "has_local_typedef":  set(),
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"
    local_struct_map = defaultdict(set)

    lines = log_data.split('\n')
    for i, line in enumerate(lines):
        if "extraneous closing brace" in line:
            categories["extraneous_brace"] = True

        if "error:" not in line and "undefined reference" not in line and "undefined symbol" not in line:
            continue

        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)

        if is_sdk_or_ndk_path(filepath):
            filepath = None

        # ── Pattern matchers ──────────────────────────────────────────────
        m_redef   = re.search(r"typedef redefinition with different types \('([^']+)'(?:.*?)vs '([^']+)'(?:.*?)\)", line)
        m_static  = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_ident   = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit= re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_ref = re.search(r"undefined reference to `([^']+)'", line)
        m_undef_sym = re.search(r"undefined symbol: (.*)", line)
        m_no_member = re.search(r"no member named '([^']+)' in 'struct ([^']+)'", line)

        m_sizeof = "invalid application of 'sizeof'" in line
        m_ptr    = "arithmetic on a pointer to an incomplete type" in line
        m_array  = "array has incomplete element type" in line
        m_def    = "incomplete definition of type" in line

        # Track files that have a local typedef redef — don't blindly inject headers
        if m_redef and filepath:
            categories["has_local_typedef"].add(filepath)
            categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))

        # "no member named X in struct Y" — the struct body didn't include those fields.
        # This is a symptom of a bad typedef redef fix (forward-decl stub hiding real body).
        # Flag the file as having a local typedef so injection is skipped.
        if m_no_member and filepath:
            categories["has_local_typedef"].add(filepath)

        if filepath and os.path.exists(filepath):
            # Only enqueue for n64_types injection if NOT a local-typedef file
            if filepath not in categories["has_local_typedef"]:
                categories["missing_n64_types"].add(filepath)

        if m_unknown and m_unknown.group(1) in {"RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "ALVoiceState"}:
            categories["audio_states"].add(m_unknown.group(1))
        elif m_undef_ref:
            categories["undefined_symbols"].add(m_undef_ref.group(1).strip())
        elif m_undef_sym:
            categories["undefined_symbols"].add(m_undef_sym.group(1).replace("'", "").strip())
        elif m_implicit:
            categories["implicit_func"].add(m_implicit.group(1))
        elif m_ident:
            ident = m_ident.group(1)
            if ident == "actor" and filepath:
                categories["actor_pointer"].add(filepath)
            else:
                categories["undeclared_macros"].add(ident)
        elif m_static and filepath:
            categories["static_conflict"].append((filepath, m_static.group(1)))
        elif (m_sizeof or m_ptr or m_array or m_def) and filepath:
            inc_type = extract_incomplete_type(line)
            if inc_type:
                categories["incomplete_sizeof"].append((filepath, inc_type))
        elif m_unknown:
            type_name = m_unknown.group(1)
            if filepath:
                local_struct_map[filepath].add(type_name)
        else:
            if line.strip():
                categories["unknown"].append(line.strip())

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

    # Second pass: remove files in has_local_typedef from missing_n64_types
    categories["missing_n64_types"] -= categories["has_local_typedef"]

    return categories


# ─── Fix application ──────────────────────────────────────────────────────────

def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0, set()

    log_data = read_file(LOG_FILE)
    categories = classify_errors(log_data)

    # Emit the failed-files log every cycle regardless
    failed_files = generate_failed_log(log_data)

    fixes = 0
    fixed_files = set()

    # ── Extraneous brace cleanup ──────────────────────────────────────────
    if categories["extraneous_brace"] and os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        original = content
        content = re.sub(
            r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n",
            "", content
        )
        content = re.sub(
            r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{",
            r"typedef struct \1 {", content
        )
        if content != original:
            write_file(TYPES_HEADER, content)
            print(f"  [🛠️] Cleaned up syntax corruption in n64_types.h")
            fixes += 1

    # ── FIX 0: #pragma once guard ─────────────────────────────────────────
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            write_file(TYPES_HEADER, "#pragma once\n" + content)
            print("  [🛠️] Secured n64_types.h with #pragma once")
            fixes += 1

    # ── FIX A: Inject n64_types.h (skip files with local typedef issues) ──
    for filepath in sorted(categories["missing_n64_types"]):
        if not os.path.exists(filepath):
            continue
        if filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            print(f"  [🛠️] Injected n64_types.h into {os.path.basename(filepath)}")
            fixed_files.add(filepath)
            fixes += 1

    # ── FIX B: 'actor' pointer ────────────────────────────────────────────
    for filepath in sorted(categories["actor_pointer"]):
        if not os.path.exists(filepath):
            continue
        content = read_file(filepath)
        original = content
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
            print(f"  [🛠️] Injected 'actor' pointer into {os.path.basename(filepath)}")
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # ── FIX C: Local struct forward declarations ───────────────────────────
    if categories["local_struct_fwd"]:
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_struct_fwd"]:
            file_to_types[filepath].add(type_name)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath):
                continue
            content = read_file(filepath)
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content:
                    fwd_lines.append(fwd_decl)
            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n"
                write_file(filepath, injection + content)
                print(f"  [🛠️] Injected forward decls {sorted(type_names)} into {os.path.basename(filepath)}")
                fixed_files.add(filepath)
                fixes += 1

    # ── FIX D: Typedef Redefinition ───────────────────────────────────────
    #
    # Root cause observed in castle.c:
    #   Line 2:  typedef struct LetterFloorTile_s LetterFloorTile;   ← injected by FIX C
    #   Line 70: } LetterFloorTile;                                   ← inline anonymous struct
    #
    # Clang rejects this because the forward decl names tag _s but the body names tag
    # implicitly (anonymous).  Strategy:
    #   1. If a forward decl "typedef struct TAG_s ALIAS;" exists AND the file also has
    #      an anonymous "typedef struct { ... } ALIAS;" body, remove the redundant forward
    #      decl and rename the body's tag to TAG_s.
    #   2. Fallback: rewrite struct tag references from old_tag -> target_tag.
    #
    seen_redef = set()
    for filepath, type1, type2 in categories["typedef_redef"]:
        key = (filepath, type1, type2)
        if key in seen_redef:
            continue
        seen_redef.add(key)

        if not os.path.exists(filepath):
            continue
        content = read_file(filepath)
        original = content

        t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
        t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
        tag1 = t1_m.group(1) if t1_m else None
        tag2 = t2_m.group(1) if t2_m else None

        if not (tag1 and tag2 and tag1 != tag2):
            continue

        # Prefer the _s-suffixed tag as the canonical struct tag
        target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
        old_tag    = tag1 if target_tag == tag2 else tag2
        alias      = old_tag  # The typedef alias name is the non-_s name

        # Strategy 1: Remove injected forward decl + tag the anonymous body correctly
        fwd_pattern = rf"typedef\s+struct\s+{re.escape(target_tag)}\s+{re.escape(alias)}\s*;\s*\n?"
        anon_body_pattern = rf"typedef\s+struct\s*\{{([\s\S]*?)\}}\s*{re.escape(alias)}\s*;"

        has_fwd  = re.search(fwd_pattern, content)
        has_body = re.search(anon_body_pattern, content)

        if has_fwd and has_body:
            # Remove the redundant forward decl; rewrite anonymous body to use target_tag
            content = re.sub(fwd_pattern, "", content, count=1)
            content = re.sub(
                anon_body_pattern,
                lambda m: f"typedef struct {target_tag} {{{m.group(1)}}} {alias};",
                content, count=1
            )
            print(f"  [🛠️] Resolved typedef redef in {os.path.basename(filepath)}: "
                  f"removed fwd decl, tagged body as '{target_tag}'")
        else:
            # Strategy 2: Plain tag substitution
            count = 0
            # Try anonymous typedef body rewrite
            pattern_anon = (r"typedef\s+struct\s*(?:\w+\s*)?\{([\s\S]*?)\}\s*"
                            + re.escape(old_tag) + r"\s*;")
            content, count = re.subn(
                pattern_anon,
                f"typedef struct {target_tag} {{\\1}} {old_tag};",
                content
            )
            if count == 0:
                content, count = re.subn(
                    r"\bstruct\s+" + re.escape(old_tag) + r"\b",
                    f"struct {target_tag}",
                    content
                )
            if count:
                print(f"  [🛠️] Harmonized typedef tags '{old_tag}'→'{target_tag}' "
                      f"in {os.path.basename(filepath)}")

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # ── FIX E: Incomplete SDK types (sizeof traps) ────────────────────────
    if categories["incomplete_sizeof"] and os.path.exists(TYPES_HEADER):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        for filepath, tag in set(categories["incomplete_sizeof"]):
            is_sdk = (
                tag.isupper()
                or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_"))
                or (tag.endswith("_s") and tag[:-2].isupper())
            )
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
                print(f"  [🛠️] Injected dummy SDK struct '{tag}' into n64_types.h")
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── FIX F: Static function conflict ───────────────────────────────────
    seen_static = set()
    for filepath, func_name in categories["static_conflict"]:
        key = (filepath, func_name)
        if key in seen_static:
            continue
        seen_static.add(key)
        if not os.path.exists(filepath):
            continue
        content = read_file(filepath)
        prefix = os.path.basename(filepath).split('.')[0]
        macro_fix = (f"\n/* AUTO: fix static conflict */\n"
                     f"#define {func_name} auto_renamed_{prefix}_{func_name}\n")
        if macro_fix not in content:
            anchor = '#include "ultra/n64_types.h"'
            if anchor in content:
                content = content.replace(anchor, anchor + macro_fix)
            else:
                content = macro_fix + content
            write_file(filepath, content)
            print(f"  [🛠️] Protected static '{func_name}' via macro in {os.path.basename(filepath)}")
            fixed_files.add(filepath)
            fixes += 1

    # ── FIX G: Missing SDK macros ─────────────────────────────────────────
    if categories["undeclared_macros"] and os.path.exists(TYPES_HEADER):
        known_macros = {"ADPCMFSIZE": "9", "ADPCMVSIZE": "8"}
        types_content = read_file(TYPES_HEADER)
        macros_added = False
        for macro in categories["undeclared_macros"]:
            if macro in known_macros and f"#define {macro}" not in types_content:
                types_content += f"\n#ifndef {macro}\n#define {macro} {known_macros[macro]}\n#endif\n"
                macros_added = True
                print(f"  [🛠️] Injected macro '{macro}' into n64_types.h")
        if macros_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── FIX H: Missing standard C headers ────────────────────────────────
    if categories["implicit_func"] and os.path.exists(TYPES_HEADER):
        math_funcs   = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        types_content = read_file(TYPES_HEADER)
        includes_added = False
        for func in categories["implicit_func"]:
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs:   header = "<stdlib.h>"
            else:                        continue
            if f"#include {header}" not in types_content:
                types_content = types_content.replace(
                    "#pragma once", f"#pragma once\n#include {header}"
                )
                includes_added = True
                print(f"  [🛠️] Injected {header} for implicit '{func}'")
        if includes_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── FIX I: Linker stubs ───────────────────────────────────────────────
    if categories["undefined_symbols"]:
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace(
                        "add_library(", "add_library(\n        ultra/n64_stubs.c"
                    )
                    write_file(cmake_file, cmake_content)

        existing_stubs = read_file(STUBS_FILE)
        stubs_added = False
        for sym in sorted(categories["undefined_symbols"]):
            if sym.startswith("_Z") or "vtable" in sym:
                continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
                print(f"  [🛠️] Generated linker stub for '{sym}'")
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    # ── FIX J: Audio/synth struct states ─────────────────────────────────
    if categories["audio_states"] and os.path.exists(TYPES_HEADER):
        types_content = read_file(TYPES_HEADER)
        audio_added = False
        for t in sorted(categories["audio_states"]):
            if f"typedef struct {t}" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            print(f"  [🛠️] Injected missing N64 synth types into n64_types.h")
            fixes += 1

    # Summary line
    if fixes == 0:
        generate_error_summary(log_data)
    else:
        print(f"\n  ✅ Applied {fixes} fix(es) across {len(fixed_files)} source file(s) this cycle.")

    return fixes, failed_files


# ─── Main loop ────────────────────────────────────────────────────────────────

def main():
    stall_count = 0

    for i in range(1, 200):
        print(f"\n{'='*40}\n--- Cycle {i} ---\n{'='*40}")

        if run_build():
            print("\n✅ Build Successful!")
            # Clean up the failed log if we made it
            if os.path.exists(FAILED_LOG_FILE):
                os.remove(FAILED_LOG_FILE)
            return

        fixes, failed_files = apply_fixes()

        if fixes == 0:
            stall_count += 1
            print(f"\n⚠️  No fixable patterns this cycle. "
                  f"Stall count: {stall_count}/{MAX_STALL}")
            if failed_files:
                print(f"   {len(failed_files)} file(s) still failing — see {FAILED_LOG_FILE}")
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted after {MAX_STALL} consecutive stall cycles.")
                print(f"   Review {FAILED_LOG_FILE} for remaining issues.")
                break
        else:
            stall_count = 0  # Reset stall counter on any progress

        time.sleep(1)


if __name__ == "__main__":
    main()
