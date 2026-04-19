import os
import re
from collections import defaultdict

# --- PATH CONFIGURATION ---
LOGIC_DIR = "scripts/conversion_logic"

BRACE_MATCH = r"[^{}]*"
for _ in range(4):
    BRACE_MATCH = r"(?:[^{}]|\{" + BRACE_MATCH + r"\})*"

# Initialize dictionaries (Will be populated dynamically)
N64_STRUCT_BODIES = {}
KNOWN_MACROS = {}
KNOWN_FUNCTION_MACROS = {}
OPAQUE_TYPES = set()
REPLACEMENTS = {}

def load_external_logic():
    """Dynamically ingests drop-in logic files from the conversion_logic directory."""
    global N64_STRUCT_BODIES, KNOWN_MACROS, OPAQUE_TYPES, REPLACEMENTS
    
    if not os.path.exists(LOGIC_DIR):
        print(f"⚠️ Warning: Logic directory {LOGIC_DIR} not found.")
        return

    # 1. Load Macros (KEY = VALUE)
    macro_path = os.path.join(LOGIC_DIR, "macros.txt")
    if os.path.exists(macro_path):
        with open(macro_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    KNOWN_MACROS[k.strip()] = v.strip()

    # 2. Load Types/Structs (Multi-line parsing)
    # Expected format: TYPE_NAME { body }
    types_path = os.path.join(LOGIC_DIR, "types.txt")
    if os.path.exists(types_path):
        content = open(types_path, 'r').read()
        # Regex to find TypeName { content } blocks
        matches = re.finditer(r'([A-Za-z0-9_]+)\s*\{([\s\S]*?)\}', content)
        for m in matches:
            tag, body = m.group(1), m.group(2).strip()
            # Wrap in typedef if not already present in the text file
            if "typedef" not in body:
                N64_STRUCT_BODIES[tag] = f"typedef struct {tag}_s {{ {body} }} {tag};"
            else:
                N64_STRUCT_BODIES[tag] = body

    # 3. Load Opaque Types (List)
    opaque_path = os.path.join(LOGIC_DIR, "opaque.txt")
    if os.path.exists(opaque_path):
        with open(opaque_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    OPAQUE_TYPES.add(line.strip())

    # 4. Load Replacements (OLD -> NEW)
    rep_path = os.path.join(LOGIC_DIR, "replacements.txt")
    if os.path.exists(rep_path):
        with open(rep_path, 'r') as f:
            for line in f:
                if '->' in line:
                    old, new = line.split('->', 1)
                    REPLACEMENTS[old.strip()] = new.strip()

# Initialize Logic
load_external_logic()

# Hardcoded Fallbacks (Only if not found in .txt files)
if "Mtx" not in N64_STRUCT_BODIES:
    N64_STRUCT_BODIES["Mtx"] = "typedef union { struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;"

POSIX_RESERVED_NAMES = {
    "close", "open", "read", "write", "send", "recv",
    "connect", "accept", "bind", "listen", "select",
    "poll", "dup", "dup2", "fork", "exec", "exit",
    "stat", "fstat", "lstat", "access", "unlink", "rename",
    "mkdir", "rmdir", "chdir", "getcwd", "getpid", "getppid",
    "getuid", "getgid", "signal", "raise", "kill",
    "printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf",
    "time", "clock", "sleep", "usleep", "malloc", "calloc", "realloc", "free",
    "memcpy", "memset", "memmove", "memcmp", "strlen", "strcpy", "strncpy",
    "strcmp", "strncmp", "strcat", "strncat", "strchr", "strrchr", "strstr",
    "atoi", "atol", "atof", "strtol", "strtod",
    "abs", "labs", "fabs", "sqrt", "pow", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "rand", "srand",
}

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f: return f.read()
    except: return ""

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(content)

def extract_incomplete_type(line):
    m = re.search(r"incomplete (?:element )?type '(?:struct\s+)?([^']+)'", line)
    if m: return m.group(1)
    m = re.search(r"\(aka '(?:struct\s+)?([^']+)'\)", line)
    return m.group(1) if m else None

def source_path(path):
    if not path: return None
    p = path.replace("C/C++: ", "").strip()
    if "Banjo-recomp-android/" in p:
        p = p.split("Banjo-recomp-android/")[-1]
    return os.path.normpath(p)

def is_sdk_or_ndk_path(fp):
    if not fp: return True
    normalized = fp.replace("\\", "/")
    return any(x in normalized.lower() for x in ["/usr/", "ndk", "libraries/adk"])

def is_defined_locally(filepath, tag):
    if not filepath or not os.path.exists(filepath): return False
    c = read_file(filepath)
    pattern1 = rf"typedef\s+(?:struct|union)[^{{]*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(tag)}\b[^;]*;"
    pattern2 = rf"(?:struct|union)\s+{re.escape(tag)}\s*\{{({BRACE_MATCH})\}}"
    return bool(re.search(pattern1, c) or re.search(pattern2, c))

def classify_errors(log_data):
    """
    Unified classification engine. 
    This is now the single source of truth for both the driver and the conversion engine.
    """
    categories = {
        "missing_types": set(),
        "undeclared_identifiers": set(),
        "implicit_func_stubs": set(),
        "need_struct_body": set(),
        "struct_redef": [],
        "typedef_redef": [],
        "posix_reserved_conflict": [],
        "errno_conflict": set(),
        "missing_members": set(),
        "undefined_symbols": set(),
        "incomplete_sizeof": [],
        "redefinition": set(),
        "conflicting_types": set(),
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    for line in log_data.split('\n'):
        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)
        if is_sdk_or_ndk_path(filepath): filepath = None

        # 🔧 Regex: Member access into incomplete type (Missing struct body)
        m_inc = re.search(r"member access into incomplete type '(?:struct|union )?(\w+)'", line)
        if m_inc: categories["need_struct_body"].add(m_inc.group(1))

        # 🔧 Regex: Unknown type name (Missing typedef or header)
        m_type = re.search(r"unknown type name '(\w+)'", line)
        if m_type:
            t = m_type.group(1)
            if t in N64_STRUCT_BODIES: categories["need_struct_body"].add(t)
            elif filepath: categories["missing_types"].add((filepath, t))

        # 🔧 Regex: Undeclared identifier (Missing Macro or Global)
        m_ident = re.search(r"use of undeclared identifier '(\w+)'", line)
        if m_ident:
            ident = m_ident.group(1)
            if ident in KNOWN_MACROS: categories["undeclared_identifiers"].add(ident)
            elif ident.isupper(): categories["undeclared_identifiers"].add(ident)
            elif filepath: categories["missing_types"].add((filepath, ident)) # Treat as possible type

        # 🔧 Regex: Implicit function (Missing Prototype)
        m_func = re.search(r"implicit declaration of function '(\w+)'", line)
        if m_func: categories["implicit_func_stubs"].add(m_func.group(1))

        # 🔧 Regex: Redefinitions
        if "redefinition of" in line and filepath:
            m_re = re.search(r"redefinition of '(\w+)'", line)
            if m_re: categories["struct_redef"].append((filepath, m_re.group(1)))

        # 🔧 Regex: Errno/Errnum conflicts
        if "error:" in line and "errno" in line:
            if filepath: categories["errno_conflict"].add(filepath)

    return categories
