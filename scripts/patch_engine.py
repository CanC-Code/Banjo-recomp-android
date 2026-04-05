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
# We inject opaque stubs so files that only use pointers to them can compile.
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
    """Read a file safely, replacing invalid characters."""
    with open(filepath, 'r', errors='replace') as f:
        return f.read()

def write_file(filepath, content):
    """Write content to a specified filepath."""
    with open(filepath, 'w') as f:
        f.write(content)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# ---------------------------------------------------------------------------
# Safe unpackers — tolerate any shape from the error parser
# ---------------------------------------------------------------------------

def _safe_str(v):
    return v if isinstance(v, str) else ""

def _unpack_typedef_redef_item(item):
    """Unpack up to 3 elements for typedef redefinition items."""
    if isinstance(item, (list, tuple)) and len(item) >= 3:
        return str(item[0]), _safe_str(item[1]), _safe_str(item[2])
    if isinstance(item, (list, tuple)) and len(item) == 2:
        return str(item[0]), _safe_str(item[1]), ""
    return str(item), "", ""

def _unpack_pair(item):
    """Unpack exactly 2 elements safely."""
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return str(item[0]), _safe_str(item[1])
    return str(item), ""

# ---------------------------------------------------------------------------
# Preamble stripping
# ---------------------------------------------------------------------------

def strip_auto_preamble(content):
    """Remove auto-injected forward-declaration blocks to prevent duplicates."""
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
    """Ensure n64_types.h exists and has a #pragma once guard."""
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
            write_file(TYPES_HEADER, content)
        return content
    content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
    os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)
    write_file(TYPES_HEADER, content)
    return content

# ---------------------------------------------------------------------------
# Dynamic struct utilities
# ---------------------------------------------------------------------------

def canonical_tag(name):
    """
    Derive the expected _s struct tag for a typedef alias.
    e.g., sChVegetable -> chVegetable_s
    """
    if len(name) > 1 and name[0].islower() and name[1].isupper():
        base = name[1].lower() + name[2:]
        return base + "_s"
    return name + "_s"

def remove_conflicting_fwd_decl(content, alias):
    """Remove a forward-decl we injected when the full body now exists."""
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
    """
    Rewrite a struct body tag to match canonical naming if it conflicts.
    """
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
    """
    Inject a #define that renames func_name to a file-local alias so that
    the static definition no longer clashes with the POSIX extern prototype.
    """
    prefix    = os.path.basename(filepath).split('.')[0]
    new_name  = f"n64_{prefix}_{func_name}"
    define    = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    
    if define in content:
        return content, False
        
    # Insert right after the last #include, or at the top
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    if includes:
        idx = includes[-1].end()
    else:
        idx = 0
    return content[:idx] + define + content[idx:], True

# ---------------------------------------------------------------------------
# Main fix dispatcher
# ---------------------------------------------------------------------------

def apply_fixes(categories):
    """Iterate parsed compilation errors and apply automatic code fixes."""
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
                # Omitted: regex for deleting entirely based on global known logic.
                continue

            new_content, tag_fixed = fix_body_tag(content, alias)
            if tag_fixed:
                content = new_content
                content, _ = remove_conflicting_fwd_decl(content, alias)
                continue

            # BUG 1 FIX: Splitting body into two explicit capture groups to avoid IndexError
            anon_pat = (
                r"typedef\s+struct\s*\{([^{}]*)\}\s*([^;]*\b"
                + re.escape(alias) + r"\b[^;]*);"
            )
            
            if re.search(anon_pat, content, re.DOTALL):
                def _anon_sub(m, tt=target_tag):
                    body_inner = m.group(1) # Group 1: Interior of struct
                    declarator = m.group(2) # Group 2: Alias string declarator
                    return f"typedef struct {tt} {{{body_inner}}} {declarator};"
                content, _ = re.subn(anon_pat, _anon_sub, content, flags=re.DOTALL)
            else:
                content, _ = re.subn(
                    r"\bstruct\s+" + re.escape(alias) + r"\b",
                    f"struct {target_tag}", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath); fixes += 1

    # 12b. N64 DSP audio state types (BUG 2 FIX)
    if categories.get("unknown_audio_state_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        for t in sorted(categories["unknown_audio_state_types"]):
            if not isinstance(t, str): continue
            if t not in N64_AUDIO_STATE_TYPES: continue
            if f"typedef struct {t}" not in types_content and f"}} {t};" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
                added = True
        if added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    if categories.get("missing_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        mt = categories["missing_types"]
        if not isinstance(mt, (list, set, tuple)): mt = []
        for item in sorted(mt, key=str):
            tag = item[1] if isinstance(item, tuple) and len(item) >= 2 else item
            if not isinstance(tag, str): continue
            if tag in N64_AUDIO_STATE_TYPES:
                if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                    types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                    added = True
        if added:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 20. POSIX reserved name conflicts detected by build_driver's parser (BUG 3 FIX)
    if categories.get("posix_reserved_conflict"):
        for item in categories.get("posix_reserved_conflict", []):
            filepath, func_name = _unpack_pair(item)
            if not func_name or not os.path.exists(filepath): continue
            if func_name not in POSIX_RESERVED_NAMES: continue
            
            content = read_file(filepath)
            new_content, changed = _rename_posix_static(content, func_name, filepath)
            if changed:
                write_file(filepath, new_content)
                fixed_files.add(filepath); fixes += 1

    return fixes, fixed_files
