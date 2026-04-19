import os
import re
from collections import defaultdict

LOGIC_DIR = "scripts/conversion_logic"

# Hardcoded primitives for normalization
TYPE_MAP = {
    r'\bunsigned long long\b': 'u64',
    r'\blong long int\b':      's64',
    r'\bunsigned int\b':       'u32',
    r'\bsigned int\b':         's32',
    r'\bunsigned short\b':      'u16',
    r'\bunsigned char\b':      'u8',
    r'\bsigned char\b':        's8',
    r'\bshort\b':              's16',
    r'\bint\b':                's32', # Mapping standard int to s32 for N64 consistency
}

def normalize_primitives(text):
    """Ensures external definitions use the project's fixed-width N64 types."""
    for pattern, replacement in TYPE_MAP.items():
        text = re.sub(pattern, replacement, text)
    return text

def load_external_logic():
    global N64_STRUCT_BODIES, KNOWN_MACROS
    
    if not os.path.exists(LOGIC_DIR):
        return

    # 🔧 Refined Types Ingestion for "Key = Value" format
    types_path = os.path.join(LOGIC_DIR, "types.txt")
    if os.path.exists(types_path):
        with open(types_path, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    # Split into the Type Name and the actual C code
                    tag, body = line.split('=', 1)
                    clean_tag = tag.strip()
                    # Normalize the C code to use u32, s16, etc.
                    clean_body = normalize_primitives(body.strip())
                    
                    # If the user provided a full typedef, use it as is.
                    # Otherwise, wrap it to ensure it's a valid C statement.
                    if "typedef" not in clean_body:
                        N64_STRUCT_BODIES[clean_tag] = f"typedef struct {clean_tag}_s {{ {clean_body} }} {clean_tag};"
                    else:
                        N64_STRUCT_BODIES[clean_tag] = clean_body

    # 🔧 Macros Ingestion
    macro_path = os.path.join(LOGIC_DIR, "macros.txt")
    if os.path.exists(macro_path):
        with open(macro_path, 'r') as f:
            for line in f:
                if '=' in line:
                    k, v = line.split('=', 1)
                    KNOWN_MACROS[k.strip()] = v.strip()

# ... [Rest of the helper functions from previous turn] ...

# Initialize Logic on Import
N64_STRUCT_BODIES = {}
KNOWN_MACROS = {}
load_external_logic()
