import os
import re
from collections import defaultdict

# --- PATH CONFIGURATION ---
LOGIC_DIR = "scripts/conversion_logic"

BRACE_MATCH = r"[^{}]*"
for _ in range(4):
    BRACE_MATCH = r"(?:[^{}]|\{" + BRACE_MATCH + r"\})*"

# Dynamic Logic Containers
N64_STRUCT_BODIES = {}
KNOWN_MACROS = {}
KNOWN_FUNCTION_MACROS = {}
OPAQUE_TYPES = set()
REPLACEMENTS = {}

def load_external_logic():
    """Ingests the specific Name = Typedef; format from your conversion files."""
    global N64_STRUCT_BODIES, KNOWN_MACROS, OPAQUE_TYPES, REPLACEMENTS
    
    if not os.path.exists(LOGIC_DIR):
        return

    # 1. Parse macros.txt (KEY = VALUE)
    macro_path = os.path.join(LOGIC_DIR, "macros.txt")
    if os.path.exists(macro_path):
        with open(macro_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    k, v = line.split('=', 1)
                    KNOWN_MACROS[k.strip()] = v.strip()

    # 2. Parse types.txt (Tag = typedef ... ;)
    # This handles your multi-part definitions for Vtx and OSThread
    types_path = os.path.join(LOGIC_DIR, "types.txt")
    if os.path.exists(types_path):
        with open(types_path, 'r') as f:
            for line in f:
                if '=' in line and line.strip() and not line.strip().startswith('#'):
                    tag, definition = line.split('=', 1)
                    # We store the raw C string to be injected directly into headers
                    N64_STRUCT_BODIES[tag.strip()] = definition.strip()

    # 3. Parse opaque.txt (Simple List)
    opaque_path = os.path.join(LOGIC_DIR, "opaque.txt")
    if os.path.exists(opaque_path):
        with open(opaque_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    OPAQUE_TYPES.add(line.strip())

# Initialize the logic engine
load_external_logic()

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

def classify_errors(log_data):
    """
    Scans the build log and populates categories.
    These categories will be used by apply_fixes() in source_conversion.py
    """
    categories = {
        "missing_types": set(),
        "undeclared_identifiers": set(),
        "implicit_func_stubs": set(),
        "need_struct_body": set(),
        "struct_redef": [],
        "typedef_redef": [],
        "errno_conflict": set(),
        "missing_members": set(),
        "undefined_symbols": set(),
        "incomplete_sizeof": [],
    }

    file_regex = r"((?:/[^:\s]+)+\.(?:c|cpp|h|cc|cxx)):"

    for line in log_data.split('\n'):
        m_file = re.search(file_regex, line)
        filepath = source_path(m_file.group(1) if m_file else None)
        if is_sdk_or_ndk_path(filepath): filepath = None

        # Detect incomplete types (The catalyst for injecting your types.txt definitions)
        m_inc = re.search(r"incomplete (?:definition|type) '(?:struct |union )?(\w+)'", line)
        if m_inc:
            tag = m_inc.group(1)
            # If we have a drop-in definition, use it; otherwise, let the engine stub it.
            categories["need_struct_body"].add(tag)

        # Detect unknown types
        m_type = re.search(r"unknown type name '(\w+)'", line)
        if m_type:
            tag = m_type.group(1)
            if tag in N64_STRUCT_BODIES:
                categories["need_struct_body"].add(tag)
            elif filepath:
                categories["missing_types"].add((filepath, tag))

        # Detect member access errors (Often means the struct is a stub and needs your types.txt body)
        m_member = re.search(r"no member named '(\w+)' in '(?:struct |union )?(\w+)'", line)
        if m_member:
            member, struct_name = m_member.group(1), m_member.group(2)
            if struct_name in N64_STRUCT_BODIES:
                categories["need_struct_body"].add(struct_name)
            else:
                categories["missing_members"].add((struct_name, member))

    return categories
