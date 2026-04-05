import os
import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Known-data tables
# ---------------------------------------------------------------------------

BRACE_MATCH = r"[^{}]*"

N64_STRUCT_BODIES = {
    "Mtx": "typedef struct Mtx_s {\n    float m[4][4];\n} Mtx;"
}

KNOWN_MACROS = {
    "OS_IM_1": "0x0001",
    "OS_IM_2": "0x0002",
}

KNOWN_FUNCTION_MACROS = {
    "some_macro": "#define some_macro(x) ((x) * 2)"
}

KNOWN_GLOBAL_TYPES = {"Actor", "Mtx"}

# N64 audio DSP state types defined in synthInternals.h.
N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
    "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
    "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

# POSIX / libc reserved function names that collide with N64 source static fns.
POSIX_RESERVED_NAMES = {
    "close", "open", "read", "write", "send", "recv",
    "connect", "accept", "bind", "listen", "select",
    "poll", "dup", "dup2", "fork", "exec", "exit",
    "stat", "fstat", "lstat", "access", "unlink", "rename",
    "mkdir", "rmdir", "chdir", "getcwd",
    "getpid", "getppid", "getuid", "getgid",
    "signal", "raise", "kill",
    "printf", "fprintf", "sprintf", "snprintf",
    "scanf", "fscanf", "sscanf",
    "time", "clock", "sleep", "usleep",
    "malloc", "calloc", "realloc", "free",
    "memcpy", "memset", "memmove", "memcmp",
    "strlen", "strcpy", "strncpy", "strcmp", "strncmp",
    "strcat", "strncat", "strchr", "strrchr", "strstr",
    "atoi", "atol", "atof", "strtol", "strtod",
    "abs", "labs", "fabs", "sqrt", "pow",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "rand", "srand",
}

# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def read_file(filepath):
    with open(filepath, 'r', errors='replace') as f:
        return f.read()

def write_file(filepath, content):
    with open(filepath, 'w') as f:
        f.write(content)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# ---------------------------------------------------------------------------
# Safe unpackers
# ---------------------------------------------------------------------------

def _safe_str(v):
    return v if isinstance(v, str) else ""

def _unpack_typedef_redef_item(item):
    if isinstance(item, (list, tuple)) and len(item) >= 3:
        return str(item[0]), _safe_str(item[1]), _safe_str(item[2])
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return str(item[0]), _safe_str(item[1]), ""
    return str(item), "", ""

def _unpack_pair(item):
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return str(item[0]), _safe_str(item[1])
    return str(item), ""

# ---------------------------------------------------------------------------
# Preamble stripping
# ---------------------------------------------------------------------------

def strip_auto_preamble(content):
    lines = content.split('\n')
    result = []
    in_auto_block = False
    for line in lines:
        s = line.strip()
        if s.startswith("/* AUTO: forward decl"):
            in_auto_block = True
            continue
        if in_auto_block and re.match(r'(?:typedef\s+)?struct\s+\w+(?:_s)?\s+\w+\s*;', s):
            continue
        in_auto_block = False
        result.append(line)
    return '\n'.join(result)

# ---------------------------------------------------------------------------
# Types-header bootstrap
# ---------------------------------------------------------------------------

def ensure_types_header_base():
    """Ensure n64_types.h exists and injects proactive SDK audio states."""
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)
        
    # Proactively inject audio states to prevent the build from failing at all
    changed = False
    for t in N64_AUDIO_STATE_TYPES:
        if f"typedef struct {t}" not in content and f"}} {t};" not in content:
            content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
            changed = True
            
    if changed or not os.path.exists(TYPES_HEADER):
        write_file(TYPES_HEADER, content)
        
    return content

# ---------------------------------------------------------------------------
# Dynamic struct utilities
# ---------------------------------------------------------------------------

def canonical_tag(name):
    if len(name) > 1 and name[0].islower() and name[1].isupper():
        base = name[1].lower() + name[2:]
        return base + "_s"
    return name + "_s"

def remove_conflicting_fwd_decl(content, alias):
    expected_tag = canonical_tag(alias)
    pat = re.compile(
        r'/\* AUTO: forward decl[^\n]*/\n'
        r'typedef\s+struct\s+' + re.escape(expected_tag) + r'\s+' + re.escape(alias) + r'\s*;\n?'
    )
    new_content, n = pat.subn("", content)
    if n == 0:
        pat2 = re.compile(
            r'typedef\s+struct\s+' + re.escape(expected_tag) + r'\s+' + re.escape(alias) + r'\s*;\n?'
        )
        new_content, n = pat2.subn("", content)
    return new_content, n > 0

def fix_body_tag(content, alias):
    expected = canonical_tag(alias)
    pat = re.compile(
        r'(typedef\s+struct\s+)(\w+)(\s*\{[^{}]*\}\s*(?:[^;]*\b)'
        + re.escape(alias) + r'\b[^;]*;)',
        re.DOTALL
    )
    changed = False
    def _sub(m):
        nonlocal changed
        if m.group(2) == expected:
            return m.group(0)
        changed = True
        return m.group(1) + expected + m.group(3)
    new_content = pat.sub(_sub, content)
    return new_content, changed

# ---------------------------------------------------------------------------
# Rename a POSIX-reserved static function name in a source file
# ---------------------------------------------------------------------------

def _rename_posix_static(content, func_name, filepath):
    prefix    = os.path.basename(filepath).split('.')[0]
    new_name  = f"n64_{prefix}_{func_name}"
    define    = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True

# ---------------------------------------------------------------------------
# Main fix dispatcher
# ---------------------------------------------------------------------------

def apply_fixes(categories):
    fixes       = 0
    fixed_files = set()

    types_content = ensure_types_header_base()

    # 1. Extraneous brace cleanup
    if categories.get("extraneous_brace"):
        original = types_content
        types_content = re.sub(
            r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n",
            "", types_content)
        types_content = re.sub(
            r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{",
            r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 2. Conflicting implicit-type prototypes
    for item in sorted(categories.get("conflicting_types", []), key=str):
        filepath, func = _unpack_pair(item)
        if not func or not os.path.exists(filepath): continue
        content = read_file(filepath)
        pattern = r"(?:^|\n)([A-Za-z_][^;{{]*?\b{}\b\s*\([^;{{]*\))\s*{{".format(re.escape(func))
        match = re.search(pattern, content)
        if match:
            proto = match.group(1).strip() + ";"
            proto = re.sub(r'//.*', '', proto)
            proto = re.sub(r'/\*.*?\*/', '', proto, flags=re.DOTALL)
            proto = re.sub(r'\s+', ' ', proto).strip()
            if proto not in re.sub(r'\s+', ' ', content):
                includes = list(re.finditer(r"#include\s+.*?\n", content))
                injection = f"\n/* AUTO: resolve conflicting implicit type */\n{proto}\n"
                idx = includes[-1].end() if includes else 0
                content = content[:idx] + injection + content[idx:]
                write_file(filepath, content)
                fixed_files.add(filepath); fixes += 1

    # 3. Missing n64_types.h include
    for item in sorted(categories.get("missing_n64_types", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath); fixes += 1

    # 4. Actor pointer injection
    for item in sorted(categories.get("actor_pointer", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath): continue
        content = original = read_file(filepath)
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath); fixes += 1

    # 5. Local struct forward declarations
    if categories.get("local_struct_fwd"):
        file_to_types = defaultdict(set)
        for item in categories["local_struct_fwd"]:
            fp, t = _unpack_pair(item)
            if fp and t: file_to_types[fp].add(t)
        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            fwd_lines = []
            for t in sorted(type_names):
                fwd = f"typedef struct {canonical_tag(t)} {t};"
                if fwd not in content: fwd_lines.append(fwd)
            if fwd_lines:
                write_file(filepath, "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n" + content)
                fixed_files.add(filepath); fixes += 1

    # 6. Typedef / struct redefinitions
    fixd_files = set()
    for item in categories.get("typedef_redef", []):
        fp, _, _ = _unpack_typedef_redef_item(item)
        if fp: fixd_files.add(fp)
    for item in categories.get("struct_redef", []):
        fp, _ = _unpack_pair(item)
        if fp: fixd_files.add(fp)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath): continue
        content  = read_file(filepath)
        original = content
        content  = strip_auto_preamble(content)

        # Deduplicate repeated struct bodies by tag
        tagged_body_re = re.compile(
            r'(?:typedef\s+)?struct\s+(\w+)\s*\{([^{}]*)\}\s*[^;]*;', re.DOTALL)
        tag_matches = defaultdict(list)
        for m in tagged_body_re.finditer(content):
            tag_matches[m.group(1)].append(m)
        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]):
                    content = content[:m.start()] + content[m.end():]

        for item in categories.get("typedef_redef", []):
            fp2, type1, type2 = _unpack_typedef_redef_item(item)
            if fp2 != filepath: continue

            t1 = type1.replace("struct ", "").strip()
            t2 = type2.replace("struct ", "").strip()
            if t1.startswith("("): t1 = ""
            if t2.startswith("("): t2 = ""
            if not t1 and not t2: continue

            target_tag = t2 if t2.endswith("_s") else (t1 if t1.endswith("_s") else t2)
            alias      = t1 if target_tag == t2 else t2
            if not alias: continue

            if alias in KNOWN_GLOBAL_TYPES or target_tag in KNOWN_GLOBAL_TYPES:
                content = re.sub(
                    r'(?:typedef\s+)?struct\s+(?:{}|{})?\s*\{{[^{{}}]*\}}[^;]*\b{}\b[^;]*;\n?'.format(
                        re.escape(target_tag), re.escape(alias), re.escape(alias)), "", content)
                content = re.sub(
                    r'typedef\s+struct\s+(?:{}|{})\s+[^;]*\b{}\b[^;]*;\n?'.format(
                        re.escape(target_tag), re.escape(alias), re.escape(alias)), "", content)
                continue

            new_content, tag_fixed = fix_body_tag(content, alias)
            if tag_fixed:
                content = new_content
                content, _ = remove_conflicting_fwd_decl(content, alias)
                continue

            # Fully fixed explicit capture regex
            anon_pat = (
                r"typedef\s+struct\s*\{([^{}]*)\}\s*([^;]*\b"
                + re.escape(alias) + r"\b[^;]*);"
            )
            if re.search(anon_pat, content, re.DOTALL):
                def _anon_sub(m, tt=target_tag):
                    body_inner = m.group(1)
                    declarator = m.group(2)
                    return f"typedef struct {tt} {{{body_inner}}} {declarator};"
                content, _ = re.subn(anon_pat, _anon_sub, content, flags=re.DOTALL)
            else:
                content, _ = re.subn(
                    r"\bstruct\s+" + re.escape(alias) + r"\b",
                    f"struct {target_tag}", content)

        for item in categories.get("struct_redef", []):
            fp2, tag = _unpack_pair(item)
            if fp2 != filepath: continue
            if tag in KNOWN_GLOBAL_TYPES:
                content, _ = re.subn(
                    r'struct\s+{}\s*\{{[^{{}}]*\}};'.format(re.escape(tag)), "", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath); fixes += 1

    # 7. Incomplete sizeof → inject opaque body
    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen = set()
        for item in categories["incomplete_sizeof"]:
            filepath, tag = _unpack_pair(item)
            if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                c = read_file(filepath)
                if 'include "ultra/n64_types.h"' not in c:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                    fixed_files.add(filepath); fixes += 1
            if not tag or tag in seen: continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES: continue
            is_sdk = (tag.isupper() or tag.startswith(("OS","SP","DP","AL","GU","G_"))
                      or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 8. Unified Static-name conflicts
    seen_static = set()
    for cat in ["static_conflict", "posix_conflict", "posix_reserved_conflict", "static_decl_conflict"]:
        for item in categories.get(cat, []):
            filepath, func_name = _unpack_pair(item)
            key = (filepath, func_name)
            if key in seen_static: continue
            seen_static.add(key)
            if not func_name or not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            
            content = read_file(filepath)
            
            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath); fixes += 1
                continue

            prefix    = os.path.basename(filepath).split('.')[0]
            macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
            if macro_fix not in content:
                anchor  = '#include "ultra/n64_types.h"'
                content = content.replace(anchor, anchor + macro_fix) if anchor in content else macro_fix + content
                write_file(filepath, content)
                fixed_files.add(filepath); fixes += 1

    # 9. Undeclared macros
    if categories.get("undeclared_macros"):
        types_content = read_file(TYPES_HEADER)
        macros_added  = False
        for macro in sorted(categories["undeclared_macros"]):
            if not isinstance(macro, str): continue
            if macro in KNOWN_FUNCTION_MACROS:
                defn = KNOWN_FUNCTION_MACROS[macro]
                if defn not in types_content:
                    types_content += f"\n{defn}\n"; macros_added = True
            elif macro in KNOWN_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {KNOWN_MACROS[macro]}\n#endif\n"
                    macros_added = True
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 10. Implicit function declarations → add system headers
    if categories.get("implicit_func"):
        math_funcs   = {"sinf","cosf","sqrtf","abs","fabs","pow","floor","ceil","round"}
        string_funcs = {"memcpy","memset","strlen","strcpy","strncpy","strcmp","memcmp"}
        stdlib_funcs = {"malloc","free","exit","atoi","rand","srand"}
        types_content  = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if not isinstance(func, str): continue
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs:   header = "<stdlib.h>"
            else: continue
            if f"#include {header}" not in types_content:
                types_content  = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 11. Undefined linker symbols → stubs
    if categories.get("undefined_symbols"):
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace("add_library(", "add_library(\n        ultra/n64_stubs.c")
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added    = False
        for sym in sorted(categories["undefined_symbols"]):
            if not isinstance(sym, str): continue
            if sym.startswith("_Z") or "vtable" in sym: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs); fixes += 1

    # 12. Audio-state opaque types / Missing Unknown Types
    for cat in ["audio_states", "unknown_audio_state_types", "missing_types", "unknown_type", "unknown_type_name"]:
        if categories.get(cat):
            types_content = read_file(TYPES_HEADER)
            types_added   = False
            mt = categories[cat]
            if not isinstance(mt, (list, set, tuple)): mt = []
            for item in sorted(mt, key=str):
                filepath = None
                if isinstance(item, tuple) and len(item) >= 2:
                    filepath, tag = item[0], item[1]
                else:
                    tag = item
                if not isinstance(tag, str): continue
                
                # BUG 2 FIX: ALWAYS ensure the file throwing the type error has the definitions imported!
                if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                    c = read_file(filepath)
                    if 'include "ultra/n64_types.h"' not in c:
                        write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                        fixed_files.add(filepath); fixes += 1

                # If it's an audio state, we inject it dynamically and then move to the next item
                if tag in N64_AUDIO_STATE_TYPES:
                    if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                        types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                        types_added = True
                    continue

                # Standard missing type fallback stubs
                base_tag = tag[:-2] if tag.endswith("_s") else tag
                if base_tag in N64_STRUCT_BODIES or tag in KNOWN_GLOBAL_TYPES:
                    if base_tag in N64_STRUCT_BODIES:
                        nsb = categories.get("need_struct_body")
                        if isinstance(nsb, set): nsb.add(base_tag)
                        elif isinstance(nsb, list): nsb.append(base_tag)
                        else: categories["need_struct_body"] = {base_tag}
                    continue
                        
                if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                    types_content += f"\ntypedef struct {tag} {{ int dummy_data[128]; }} {tag};\n"
                    types_added = True
            if types_added:
                write_file(TYPES_HEADER, types_content); fixes += 1

    # 13. Undeclared N64 platform types (OSIntMask etc.)
    if categories.get("undeclared_n64_types"):
        types_content = read_file(TYPES_HEADER)
        k_added = False
        if "OSIntMask" in categories["undeclared_n64_types"]:
            if "OSIntMask" not in types_content:
                types_content += "\n/* N64 interrupt mask type */\ntypedef u32 OSIntMask;\n"
                k_added = True
            for macro, val in sorted(KNOWN_MACROS.items()):
                if macro.startswith("OS_IM_") and f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {val}\n#endif\n"
                    k_added = True
        if k_added:
            write_file(TYPES_HEADER, types_content); fixes += 1
        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs); fixes += 1

    # 14. Undeclared GBI constants
    if categories.get("undeclared_gbi"):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if not isinstance(ident, str): continue
            if ident in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {KNOWN_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                gbi_added = True
        if gbi_added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 16. Full struct bodies for known N64 types
    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added  = False
        nsb = categories["need_struct_body"]
        if not isinstance(nsb, (list, set, tuple)): nsb = []
        for raw_tag in sorted(nsb):
            if not isinstance(raw_tag, str): continue
            tag = raw_tag[:-2] if raw_tag.endswith("_s") else raw_tag
            if tag == "Mtx":
                categories["need_mtx_body"] = True; continue
            body = N64_STRUCT_BODIES.get(tag)
            check_str = f"typedef struct {tag}_s {{"
            needs_injection = body and (
                check_str not in types_content
                or (not body.startswith("typedef union") and f"struct {tag}_s {{" not in types_content)
            )
            if needs_injection:
                for pat in (
                    r"(?:typedef\s+)?struct\s*(?:{0}|{0}_s)?\s*\{{[^{{}}]*}}\s*[^;]*\b(?:{0}|{0}_s)\b[^;]*;\n?",
                    r"struct\s+(?:{0}|{0}_s)\s*\{{[^{{}}]*}}\s*;\n?",
                    r"typedef\s+(?:struct\s+)?(?:{0}|{0}_s)\s+[^;]*\b(?:{0}|{0}_s)\b[^;]*;\n?",
                    r"struct\s+(?:{0}|{0}_s)\s*;\n?",
                ):
                    types_content = re.sub(pat.format(re.escape(tag)), "", types_content)
                if not body.startswith("typedef union") and f"struct {tag}_s" not in body:
                    body = re.sub(
                        r"typedef\s+struct\s*(?:{})?\s*\{{".format(re.escape(tag)),
                        f"typedef struct {tag}_s {{", body, count=1)
                types_content += "\n" + body
                bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 17. Mtx special body
    if categories.get("need_mtx_body"):
        types_content = read_file(TYPES_HEADER)
        if "i[4][4]" not in types_content and "m[4][4]" not in types_content:
            for pat in (
                r"(?:typedef\s+)?struct\s*(?:Mtx|Mtx_s)?\s*\{{[^{{}}]*}}\s*[^;]*\b(?:Mtx|Mtx_s)\b[^;]*;\n?",
                r"struct\s+(?:Mtx|Mtx_s)\s*\{{[^{{}}]*}}\s*;\n?",
                r"typedef\s+(?:struct\s+)?(?:Mtx|Mtx_s)\s+[^;]*\b(?:Mtx|Mtx_s)\b[^;]*;\n?",
                r"struct\s+(?:Mtx|Mtx_s)\s*;\n?",
                r"typedef\s+union\s*\{{[^{{}}]*}}\s*__Mtx_data\s*;\n?",
                r"typedef\s+union\s*(?:Mtx|Mtx_s)?\s*\{{[^{{}}]*}}\s*[^;]*\b(?:Mtx|Mtx_s)\b[^;]*;\n?",
            ):
                types_content = re.sub(pat, "", types_content)
            types_content += "\n" + N64_STRUCT_BODIES["Mtx"]
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 18. Local forward-only declarations
    if categories.get("local_fwd_only"):
        file_to_types = defaultdict(set)
        for item in categories.get("local_fwd_only", []):
            fp, t = _unpack_pair(item)
            if fp and t: file_to_types[fp].add(t)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False

            for t in sorted(type_names):
                expected = canonical_tag(t)
                fwd_decl = f"typedef struct {expected} {t};"
                body_pat = (
                    r"typedef\s+struct\s+(\w+)\s*\{[^{}]*\}\s*[^;]*\b"
                    + re.escape(t) + r"\b[^;]*;"
                )
                body_match = re.search(body_pat, content, re.DOTALL)
                if body_match:
                    actual_tag = body_match.group(1)
                    if actual_tag != expected:
                        fixed = body_match.group(0).replace(
                            f"struct {actual_tag}", f"struct {expected}", 1)
                        content = content[:body_match.start()] + fixed + content[body_match.end():]
                        content, _ = remove_conflicting_fwd_decl(content, t)
                        changed = True
                    elif fwd_decl not in content:
                        content = f"/* AUTO: forward decl for type defined below */\n{fwd_decl}\n" + content
                        changed = True
                else:
                    if fwd_decl not in content:
                        content = f"/* AUTO: forward declarations */\n{fwd_decl}\n" + content
                        changed = True

            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath); fixes += 1

    # 19. Missing global extern declarations
    if categories.get("missing_globals"):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for glob in sorted(categories["missing_globals"]):
            if not isinstance(glob, str) or glob == "actor": continue
            if (f" {glob};" not in types_content and f"*{glob};" not in types_content
                    and f" {glob}[" not in types_content):
                decl = (f"extern void* {glob};" if glob.endswith(("_ptr","_p"))
                        else f"extern long long int {glob};")
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    return fixes, fixed_files
