import os
import re
from collections import defaultdict

# --- PATH CONFIGURATION ---
LOGIC_DIR = "scripts/conversion_logic"

BRACE_MATCH = r"[^{}]*"
for _ in range(4):
    BRACE_MATCH = r"(?:[^{}]|\{" + BRACE_MATCH + r"\})*"

N64_STRUCT_BODIES = {}
KNOWN_MACROS = {}
KNOWN_FUNCTION_MACROS = {}
OPAQUE_TYPES = set()
REPLACEMENTS = {}

def load_external_logic():
    global N64_STRUCT_BODIES, KNOWN_MACROS, OPAQUE_TYPES, REPLACEMENTS
    if not os.path.exists(LOGIC_DIR): return

    macro_path = os.path.join(LOGIC_DIR, "macros.txt")
    if os.path.exists(macro_path):
        with open(macro_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    KNOWN_MACROS[k.strip()] = v.strip()

    types_path = os.path.join(LOGIC_DIR, "types.txt")
    if os.path.exists(types_path):
        with open(types_path, 'r') as f:
            for line in f:
                if '=' in line and line.strip() and not line.strip().startswith('#'):
                    tag, definition = line.split('=', 1)
                    definition = definition.strip()
                    # AUTO-UNTANGLE: Safely split compound "typedef struct {}; typedef union {};" lines
                    if definition.count("typedef") > 1:
                        parts = re.split(r'(?<=;)\s+(?=typedef)', definition)
                        for part in parts:
                            m_tag = re.search(r'\}\s*([A-Za-z0-9_]+)\s*;', part)
                            if m_tag: N64_STRUCT_BODIES[m_tag.group(1)] = part
                    else:
                        N64_STRUCT_BODIES[tag.strip()] = definition

    opaque_path = os.path.join(LOGIC_DIR, "opaque.txt")
    if os.path.exists(opaque_path):
        with open(opaque_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'): OPAQUE_TYPES.add(line.strip())

    rep_path = os.path.join(LOGIC_DIR, "replacements.txt")
    if os.path.exists(rep_path):
        with open(rep_path, 'r') as f:
            for line in f:
                if ':::' in line and not line.strip().startswith('#'):
                    old, new = line.split(':::', 1)
                    REPLACEMENTS[old.strip()] = new.strip()

load_external_logic()

if "Mtx" not in N64_STRUCT_BODIES:
    N64_STRUCT_BODIES["Mtx"] = "typedef union { struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;"

POSIX_RESERVED_NAMES = {
    "close", "open", "read", "write", "send", "recv", "connect", "accept", "bind", "listen", "select",
    "poll", "dup", "dup2", "fork", "exec", "exit", "stat", "fstat", "lstat", "access", "unlink", "rename",
    "mkdir", "rmdir", "chdir", "getcwd", "getpid", "getppid", "getuid", "getgid", "signal", "raise", "kill",
    "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf", "time", "clock", "sleep", "usleep",
    "malloc", "calloc", "realloc", "free", "memcpy", "memset", "memmove", "memcmp", "strlen", "strcpy", "strncpy",
    "strcmp", "strncmp", "strcat", "strncat", "strchr", "strrchr", "strstr", "atoi", "atol", "atof", "strtol", "strtod",
    "abs", "labs", "fabs", "sqrt", "pow", "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "rand", "srand",
}

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f: return f.read()
    except: return ""

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(content)

def source_path(path):
    if not path: return None
    p = path.replace("C/C++: ", "").strip()
    if "Banjo-recomp-android/" in p: p = p.split("Banjo-recomp-android/")[-1]
    return os.path.normpath(p)

def is_sdk_or_ndk_path(fp):
    if not fp: return True
    return any(x in fp.replace("\\", "/").lower() for x in ["/usr/", "ndk", "libraries/adk"])

def classify_errors(log_data):
    categories = {
        "missing_types": set(), "undeclared_identifiers": set(), "implicit_func_stubs": set(),
        "need_struct_body": set(), "struct_redef": [], "typedef_redef": [], "posix_reserved_conflict": [],
        "errno_conflict": set(), "missing_members": set(), "undefined_symbols": set(), "incomplete_sizeof": [],
        "redefinition": set(), "conflicting_types": set(), "local_struct_fwd": [], "local_fwd_only": [],
        "missing_globals": set(), "implicit_func": set(), "actor_pointer": set(), "missing_n64_types": set(),
        "undeclared_macros": set(), "undeclared_gbi": set(), "static_conflict": [], 
        "linkage_conflict_funcs": set(), "linkage_conflict_files": set()
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"
    lines = log_data.split('\n')

    for i, line in enumerate(lines):
        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)
        if is_sdk_or_ndk_path(filepath): filepath = None

        # RESTORED: Multi-line linkage conflict parsing
        m_link = re.search(r"error:\s+declaration of '([A-Za-z0-9_]+)' has a different language linkage", line)
        if m_link:
            func = m_link.group(1)
            categories["linkage_conflict_funcs"].add(func)
            for j in range(i + 1, min(i + 6, len(lines))):
                m_note = re.search(r"^\s*(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+note:\s+previous declaration", lines[j])
                if m_note:
                    categories["linkage_conflict_files"].add((source_path(m_note.group(1)), func))
                    break

        if filepath:
            if "errno" in line and "error:" in line: categories["errno_conflict"].add(filepath)
            
            m_stat = re.search(r"static declaration of '(\w+)' follows non-static declaration", line)
            if m_stat:
                categories["posix_reserved_conflict"].append((filepath, m_stat.group(1)))
                categories["static_conflict"].append((filepath, m_stat.group(1)))

            m_re = re.search(r"redefinition of '(\w+)'", line)
            if m_re: categories["struct_redef"].append((filepath, m_re.group(1)))

            m_td_re = re.search(r"typedef redefinition with different types \('struct ([^']+)' vs 'struct ([^']+)'\)", line)
            if m_td_re: categories["typedef_redef"].append((filepath, f"struct {m_td_re.group(1)}", f"struct {m_td_re.group(2)}"))

        m_inc = re.search(r"member access into incomplete type '(?:struct|union )?(\w+)'", line)
        if m_inc: categories["need_struct_body"].add(m_inc.group(1))

        m_inc_def = re.search(r"incomplete (?:definition|type) '(?:struct |union )?(\w+)'", line)
        if m_inc_def: categories["need_struct_body"].add(m_inc_def.group(1))

        m_type = re.search(r"unknown type name '(\w+)'", line)
        if m_type:
            t = m_type.group(1)
            if t in N64_STRUCT_BODIES: categories["need_struct_body"].add(t)
            elif filepath: categories["missing_types"].add((filepath, t))

        m_ident = re.search(r"use of undeclared identifier '(\w+)'", line)
        if m_ident:
            ident = m_ident.group(1)
            if ident in KNOWN_MACROS or ident.isupper(): categories["undeclared_identifiers"].add(ident)
            elif filepath: categories["missing_types"].add((filepath, ident))

        m_func = re.search(r"implicit declaration of function '(\w+)'", line)
        if m_func: categories["implicit_func_stubs"].add(m_func.group(1))

        m_member = re.search(r"no member named '(\w+)' in '(?:struct |union )?(\w+)'", line)
        if m_member:
            member, struct_name = m_member.group(1), m_member.group(2)
            if struct_name in N64_STRUCT_BODIES: categories["need_struct_body"].add(struct_name)
            else: categories["missing_members"].add((struct_name, member))

    return categories
