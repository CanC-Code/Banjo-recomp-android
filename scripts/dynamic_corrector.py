"""
dynamic_corrector.py — Self-healing build driver for the BK AArch64 Android port.
v77.0 — Audio types + castle.c surgical repair edition.

Changes vs v76.0:
  - FIX D overhaul (castle.c): Previous fix produced duplicate 'LetterFloorTile_s'
    redefinitions (lines 53/60/66) by applying the body-tag rewrite multiple times
    without removing prior injected content. New strategy: detect the signature of
    a corrupted file (multiple injected typedef struct LetterFloorTile_s blocks OR
    both a forward decl AND a double-tagged body), strip ALL auto-injected preamble
    lines, and leave only the original anonymous body intact with ONE correct tagging.
  - FIX K (new): OSIntMask / OS_IM_NONE. These N64 interrupt-mask types are missing
    from n64_types.h. Injects 'typedef u32 OSIntMask;' and '#define OS_IM_NONE 0x0001'
    (N64 SDK canonical value) into n64_types.h. Also adds osSetIntMask stub.
  - FIX G expanded: known_macros now includes UNITY_PITCH (0x8000, N64 audio pitch
    unity value) and MAX_RATIO (0x8000000, N64 resampler max ratio), fixing
    n_resample.c and n_reverb.c.
  - undeclared_ident_types category: 'use of undeclared identifier' errors for
    known N64 type names (OSIntMask etc.) are now routed to FIX K rather than
    falling through to undeclared_macros.
  - FIX D guard: before applying any struct body rewrite, checks whether the file
    already has N injections and strips them first (idempotent repair).
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
    # Continue past all ninja errors so every failing file is visible in one pass
    "-Pandroid.ndk.cmakeArgs=-k 0",
]
LOG_FILE        = "Android/full_build_log.txt"
FAILED_LOG_FILE = "Android/failed_files.log"
TYPES_HEADER    = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE      = "Android/app/src/main/cpp/ultra/n64_stubs.c"

MAX_STALL = 5   # Halt after this many consecutive cycles with zero new fixes

# ── N64 interrupt mask types that appear as 'use of undeclared identifier' ──
N64_IDENT_TYPES = {
    "OSIntMask",
    "OSMesgQueue", "OSMesg", "OSThread", "OSTimer", "OSTime",
    "OSEvent", "OSPri", "OSId", "OSTask", "OSTask_t", "CPUState",
}

# ── All known N64 macros and their values ─────────────────────────────────────
KNOWN_MACROS = {
    "ADPCMFSIZE":  "9",
    "ADPCMVSIZE":  "8",
    # N64 audio DSP pitch constants (from libaudio/n_*.c)
    "UNITY_PITCH": "0x8000",        # fixed-point 1.0 for N64 resampler
    "MAX_RATIO":   "0x8000000",     # max resampler pitch ratio
    # N64 interrupt mask constants
    "OS_IM_NONE":  "0x0001",        # N64 RCP interrupt mask: none enabled
    "OS_IM_SW1":   "0x0005",
    "OS_IM_SW2":   "0x0009",
    "OS_IM_CART":  "0x0411",
    "OS_IM_PRENMI":"0x0021",
    "OS_IM_RDBWRITE":"0x0041",
    "OS_IM_RDBREAD":"0x0081",
    "OS_IM_COUNTER":"0x0101",
    "OS_IM_CPU":   "0x0201",
    "OS_IM_SP":    "0x0441",
    "OS_IM_SI":    "0x0811",
    "OS_IM_AI":    "0x1001",
    "OS_IM_VI":    "0x2001",
    "OS_IM_PI":    "0x4001",
    "OS_IM_DP":    "0x8001",
    "OS_IM_ALL":   "0xFF01",
}


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


def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ─── Failed-file log ──────────────────────────────────────────────────────────

def generate_failed_log(log_data):
    """Write Android/failed_files.log and print a summary."""
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

    with open(FAILED_LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

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
        "missing_n64_types":    set(),
        "actor_pointer":        set(),
        "local_struct_fwd":     [],
        "typedef_redef":        [],
        "struct_redef":         [],   # 'redefinition of X' (struct tag reused)
        "static_conflict":      [],
        "incomplete_sizeof":    [],
        "undeclared_macros":    set(),
        "undeclared_n64_types": set(), # OSIntMask etc. via 'undeclared identifier'
        "implicit_func":        set(),
        "undefined_symbols":    set(),
        "audio_states":         set(),
        "unknown":              [],
        "extraneous_brace":     False,
        "has_local_typedef":    set(),
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"
    local_struct_map = defaultdict(set)

    for line in log_data.split('\n'):
        if "extraneous closing brace" in line:
            categories["extraneous_brace"] = True

        if ("error:" not in line
                and "undefined reference" not in line
                and "undefined symbol" not in line):
            continue

        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)
        if is_sdk_or_ndk_path(filepath):
            filepath = None

        # ── Pattern matchers ──────────────────────────────────────────────
        m_redef     = re.search(r"typedef redefinition with different types \('([^']+)'(?:.*?)vs '([^']+)'(?:.*?)\)", line)
        m_struct_redef = re.search(r"redefinition of '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_static    = re.search(r"static declaration of '([^']+)' follows non-static declaration", line)
        m_unknown   = re.search(r"unknown type name '([A-Za-z_][A-Za-z0-9_]*)'", line)
        m_ident     = re.search(r"use of undeclared identifier '([^']+)'", line)
        m_implicit  = re.search(r"implicit declaration of function '([^']+)'", line)
        m_undef_ref = re.search(r"undefined reference to `([^']+)'", line)
        m_undef_sym = re.search(r"undefined symbol: (.*)", line)
        m_no_member = re.search(r"no member named '([^']+)' in 'struct ([^']+)'", line)

        m_sizeof = "invalid application of 'sizeof'" in line
        m_ptr    = "arithmetic on a pointer to an incomplete type" in line
        m_array  = "array has incomplete element type" in line
        m_def    = "incomplete definition of type" in line

        # Files with struct redef or typedef redef or no-member are local-typedef files
        if (m_redef or m_struct_redef or m_no_member) and filepath:
            categories["has_local_typedef"].add(filepath)

        if m_redef and filepath:
            categories["typedef_redef"].append((filepath, m_redef.group(1), m_redef.group(2)))

        if m_struct_redef and filepath:
            categories["struct_redef"].append((filepath, m_struct_redef.group(1)))

        if filepath and os.path.exists(filepath) and filepath not in categories["has_local_typedef"]:
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
            if ident in N64_IDENT_TYPES:
                # These are N64 type names that need typedef in n64_types.h
                categories["undeclared_n64_types"].add(ident)
            elif ident == "actor" and filepath:
                categories["actor_pointer"].add(filepath)
            else:
                # Could be a macro constant (OS_IM_NONE, UNITY_PITCH, MAX_RATIO...)
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
        "Acmd", "ADPCM_STATE", "Vtx", "Gfx", "Mtx",
        "RESAMPLE_STATE", "ENVMIX_STATE", "POLEF_STATE",
        "OSContPad", "OSTimer", "OSTime", "OSMesg", "OSEvent",
        "OSThread", "OSMesgQueue", "OSTask", "OSTask_t", "CPUState",
        "OSIntMask",
        "Actor", "ActorMarker",
        "s8", "u8", "s16", "u16", "s32", "u32", "s64", "u64",
        "f32", "f64", "n64_bool", "OSPri", "OSId",
    }
    for filepath, type_names in local_struct_map.items():
        for t in type_names:
            if t not in known_global_types:
                categories["local_struct_fwd"].append((filepath, t))

    # Clean missing_n64_types of any local-typedef files added before we knew
    categories["missing_n64_types"] -= categories["has_local_typedef"]

    return categories


# ─── Fix application ──────────────────────────────────────────────────────────

def apply_fixes():
    if not os.path.exists(LOG_FILE):
        return 0, set()

    log_data = read_file(LOG_FILE)
    categories = classify_errors(log_data)
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
            print("  [🛠️] Cleaned up syntax corruption in n64_types.h")
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

    # ── FIX D: Typedef / Struct Redefinition ─────────────────────────────
    #
    # Strategy for castle.c-style corruption (multiple injected bodies):
    #   1. Strip ALL auto-injected preamble lines added by prior FIX C / FIX D passes.
    #      These are lines matching:
    #        - "/* AUTO: forward declarations */"
    #        - "typedef struct X_s Y;"   (forward decl pattern)
    #        - A typedef struct block that starts with the target tag name and
    #          is NOT the original (identified as a duplicate when 2+ exist).
    #   2. Ensure the surviving body has the correct tag so Clang accepts it.
    #
    # For simpler cases (single typedef redef, no struct_redef companion):
    #   - Remove fwd decl if present + retag anon body, OR plain tag substitution.

    # Collect all files that need FIX D work (from both typedef_redef and struct_redef)
    fixd_files = set()
    for filepath, _, _ in categories["typedef_redef"]:
        fixd_files.add(filepath)
    for filepath, _ in categories["struct_redef"]:
        fixd_files.add(filepath)

    seen_redef = set()
    for filepath in sorted(fixd_files):
        if filepath in seen_redef:
            continue
        seen_redef.add(filepath)
        if not os.path.exists(filepath):
            continue

        content = read_file(filepath)
        original = content

        # ── Step 1: Strip all AUTO-injected preamble lines ────────────────
        # Remove the "/* AUTO: forward declarations */" comment block and all
        # "typedef struct FOO_s BAR;" forward-decl lines that precede the real code.
        # We strip these line-by-line from the top of the file.
        lines = content.split('\n')
        stripped_lines = []
        in_auto_block = False
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            # Remove auto-comment marker
            if stripped == "/* AUTO: forward declarations */":
                in_auto_block = True
                i += 1
                continue
            # Remove forward-decl typedef lines in the auto block
            if in_auto_block and re.match(r'typedef\s+struct\s+\w+_s\s+\w+\s*;', stripped):
                i += 1
                continue
            # Remove standalone n64_types.h include injected by FIX A into local-typedef files
            if stripped == '#include "ultra/n64_types.h"' and filepath in categories["has_local_typedef"]:
                i += 1
                in_auto_block = False
                continue
            in_auto_block = False
            stripped_lines.append(line)
            i += 1

        content = '\n'.join(stripped_lines)

        # ── Step 2: Detect duplicate typedef struct bodies and deduplicate ─
        # If the same tag appears in 2+ 'typedef struct TAG {' openings, keep only
        # the LAST one (most complete / original) and remove the earlier duplicates.
        # Pattern: typedef struct TAG_s {  ...  } Alias;
        tag_pattern = re.compile(
            r'(typedef\s+struct\s+(\w+)\s*\{[^}]*(?:\{[^}]*\}[^}]*)?\}[^;]*;)',
            re.DOTALL
        )
        # Count occurrences per tag
        tag_counts = defaultdict(list)
        for m in tag_pattern.finditer(content):
            tag_counts[m.group(2)].append(m)

        for tag, matches in tag_counts.items():
            if len(matches) > 1:
                # Remove all but the last match
                for m in matches[:-1]:
                    content = content.replace(m.group(0), "", 1)
                print(f"  [🛠️] Removed {len(matches)-1} duplicate struct body(ies) for '{tag}' in {os.path.basename(filepath)}")

        # ── Step 3: Retag anonymous body if still needed ───────────────────
        # If a forward decl "typedef struct TARGET_s ALIAS;" still exists alongside
        # an anonymous "typedef struct { ... } ALIAS;" body, fix the body tag.
        for fp2, type1, type2 in categories["typedef_redef"]:
            if fp2 != filepath:
                continue

            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2):
                continue

            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            fwd_pattern = rf"typedef\s+struct\s+{re.escape(target_tag)}\s+{re.escape(alias)}\s*;\s*\n?"
            anon_body_pattern = rf"typedef\s+struct\s*\{{([\s\S]*?)\}}\s*{re.escape(alias)}\s*;"

            has_fwd  = re.search(fwd_pattern, content)
            has_body = re.search(anon_body_pattern, content)

            if has_fwd and has_body:
                # Remove forward decl; retag body
                content = re.sub(fwd_pattern, "", content, count=1)
                content = re.sub(
                    anon_body_pattern,
                    lambda m: f"typedef struct {target_tag} {{{m.group(1)}}} {alias};",
                    content, count=1
                )
                print(f"  [🛠️] Retagged anon body as '{target_tag}' in {os.path.basename(filepath)}")
            elif not has_body:
                # Plain tag substitution fallback
                content, cnt = re.subn(
                    r"\bstruct\s+" + re.escape(alias) + r"\b",
                    f"struct {target_tag}",
                    content
                )
                if cnt:
                    print(f"  [🛠️] Tag substitution '{alias}'→'{target_tag}' in {os.path.basename(filepath)}")

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
            content = content.replace(anchor, anchor + macro_fix) if anchor in content else macro_fix + content
            write_file(filepath, content)
            print(f"  [🛠️] Protected static '{func_name}' via macro in {os.path.basename(filepath)}")
            fixed_files.add(filepath)
            fixes += 1

    # ── FIX G: Missing SDK macros (expanded) ──────────────────────────────
    if categories["undeclared_macros"] and os.path.exists(TYPES_HEADER):
        types_content = read_file(TYPES_HEADER)
        macros_added = False
        for macro in sorted(categories["undeclared_macros"]):
            if macro in KNOWN_MACROS and f"#define {macro}" not in types_content:
                types_content += f"\n#ifndef {macro}\n#define {macro} {KNOWN_MACROS[macro]}\n#endif\n"
                macros_added = True
                print(f"  [🛠️] Injected macro '{macro}' = {KNOWN_MACROS[macro]} into n64_types.h")
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
        for func in sorted(categories["implicit_func"]):
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
            print("  [🛠️] Injected missing N64 synth types into n64_types.h")
            fixes += 1

    # ── FIX K: N64 interrupt mask types (OSIntMask / OS_IM_*) ────────────
    #
    # OSIntMask is a u32 typedef. OS_IM_* are bitmask constants.
    # osSetIntMask is an N64 SDK function — stub it if missing.
    if categories["undeclared_n64_types"] and os.path.exists(TYPES_HEADER):
        types_content = read_file(TYPES_HEADER)
        k_added = False

        if "OSIntMask" in categories["undeclared_n64_types"]:
            if "typedef" not in types_content or "OSIntMask" not in types_content:
                types_content += "\n/* N64 interrupt mask type */\ntypedef u32 OSIntMask;\n"
                k_added = True
                print("  [🛠️] Injected 'OSIntMask' typedef into n64_types.h")

            # Also inject all OS_IM_* constants as macros while we're here
            for macro, val in sorted(KNOWN_MACROS.items()):
                if macro.startswith("OS_IM_") and f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {val}\n#endif\n"
                    k_added = True
                    print(f"  [🛠️] Injected '{macro}' into n64_types.h")

            # Stub osSetIntMask if it isn't already stubbed
            if os.path.exists(STUBS_FILE):
                existing_stubs = read_file(STUBS_FILE)
                if "osSetIntMask" not in existing_stubs:
                    existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { return 0; }\n"
                    write_file(STUBS_FILE, existing_stubs)
                    print("  [🛠️] Stubbed osSetIntMask in n64_stubs.c")

        if k_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ── Summary ───────────────────────────────────────────────────────────
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
            if os.path.exists(FAILED_LOG_FILE):
                os.remove(FAILED_LOG_FILE)
            return

        fixes, failed_files = apply_fixes()

        if fixes == 0:
            stall_count += 1
            print(f"\n⚠️  No fixable patterns this cycle. Stall count: {stall_count}/{MAX_STALL}")
            if failed_files:
                print(f"   {len(failed_files)} file(s) still failing — see {FAILED_LOG_FILE}")
            if stall_count >= MAX_STALL:
                print(f"\n🛑 Loop halted after {MAX_STALL} consecutive stall cycles.")
                print(f"   Review {FAILED_LOG_FILE} for remaining issues.")
                break
        else:
            stall_count = 0

        time.sleep(1)


if __name__ == "__main__":
    main()
