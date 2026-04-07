import os
import re
import logging
import sys
import subprocess
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional, Union

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"
BUILD_LOG    = "Android/build_log.txt"
BUILD_CMD    = ["./gradlew", ":app:assembleDebug"] 

# ---------------------------------------------------------------------------
# Constants & Knowledge Bases
# ---------------------------------------------------------------------------
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

PHASE_1_MACROS = {"OS_IM_NONE": "0x0000", "PI_DOMAIN1": "0", "ADPCMFSIZE": "9"}
PHASE_2_MACROS = {**PHASE_1_MACROS, "OS_READ": "0", "OS_WRITE": "1", "PI_STATUS_REG": "0x04600010"}
PHASE_3_MACROS = {**PHASE_2_MACROS, "G_ON": "1", "G_OFF": "0", "G_ZBUFFER": "0x00000001"}

_N64_OS_STRUCT_BODIES = {
    "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { s16 mi[4][4]; s16 pad; } i; } Mtx;",
    "OSMesgQueue": "typedef struct { struct OSThread_s *mtqueue; s32 validCount; OSMesg *msg; } OSMesgQueue;",
    "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; u8 type; u32 baseAddress; } OSPiHandle;",
}

SDK_DEFINES_THESE = {"OSTask", "OSScTask"}

_CORE_PRIMITIVES = """\
#include <stdint.h>
#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
typedef uint8_t  u8; typedef int8_t   s8;
typedef uint16_t u16; typedef int16_t  s16;
typedef uint32_t u32; typedef int32_t  s32;
typedef uint64_t u64; typedef int64_t  s64;
typedef float    f32; typedef double   f64;
typedef int      n64_bool;
typedef u32 OSIntMask; typedef u64 OSTime; typedef u32 OSId; typedef s32 OSPri; typedef void* OSMesg;
#endif
"""

# ---------------------------------------------------------------------------
# Utility Helpers
# ---------------------------------------------------------------------------
def read_file(filepath: str) -> str:
    if not os.path.exists(filepath): return ""
    try:
        with open(filepath, 'r', errors='replace') as f: return f.read()
    except Exception as e: return ""

def write_file(filepath: str, content: str) -> None:
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f: f.write(content)
    except Exception as e: logger.error(f"Write error {filepath}: {e}")

def normalize_path(filepath: str) -> str:
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath: return filepath.split(marker)[-1]
    return filepath.lstrip("/")

def repair_unterminated_conditionals(content: str) -> str:
    lines = content.split('\n')
    stack, remove = [], set()
    for i, line in enumerate(lines):
        if re.match(r'#\s*(?:ifndef|ifdef|if)\b', line.strip()): stack.append(i)
        elif re.match(r'#\s*endif\b', line.strip()):
            if stack: stack.pop()
    for idx in stack: remove.add(idx)
    return '\n'.join([l for i, l in enumerate(lines) if i not in remove])

def ensure_types_header_base() -> str:
    # Always ensure primitives are at the top
    content = "#pragma once\n" + _CORE_PRIMITIVES
    if os.path.exists(TYPES_HEADER):
        existing = read_file(TYPES_HEADER)
        if "CORE_PRIMITIVES_DEFINED" in existing:
            return existing
    write_file(TYPES_HEADER, content)
    return content

# ---------------------------------------------------------------------------
# Logic Engine
# ---------------------------------------------------------------------------
def run_build() -> bool:
    logger.info(f"==> Executing Build: {' '.join(BUILD_CMD)}")
    try:
        result = subprocess.run(BUILD_CMD, capture_output=True, text=True)
        write_file(BUILD_LOG, result.stdout + "\n" + result.stderr)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Build failed: {e}"); return False

def scrape_logs(categories: dict):
    if not os.path.exists(BUILD_LOG): return
    content = read_file(BUILD_LOG)
    
    # 1. Unknown type names (Captures both file and tag)
    for m in re.finditer(r"(?m)^(/[^\s:]+\.(?:c|cpp|h)[^:]*):(?:\d+):(?:\d+):\s+error:\s+unknown type name '(\w+)'", content):
        categories["missing_types"].add((normalize_path(m.group(1)), m.group(2)))
    
    # Generic fallback for unknown types
    for m in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
        tag = m.group(1)
        if not any(isinstance(x, tuple) and x[1] == tag for x in categories["missing_types"]):
            categories["missing_types"].add(tag)

    for m in re.finditer(r"error:\s+use of undeclared identifier '(\w+)'", content):
        categories["undeclared_idents"].add(m.group(1))
    for m in re.finditer(r"error:\s+implicit declaration of function '(\w+)'", content):
        categories["implicit_funcs"].add(m.group(1))
    for m in re.finditer(r"error:\s+member access into incomplete type '(?:struct )?(\w+)'", content):
        categories["need_struct_body"].add(m.group(1))

def apply_fixes(categories: dict, level: int) -> int:
    fixes = 0
    types_content = ensure_types_header_base()
    
    macros = PHASE_3_MACROS if level >= 3 else (PHASE_2_MACROS if level == 2 else PHASE_1_MACROS)
    structs = _N64_OS_STRUCT_BODIES if level >= 2 else {}

    # 1. Fix Missing Types (Fixes the TypeError)
    for item in categories["missing_types"]:
        # Unpack if tuple, else use as tag
        tag = item[1] if isinstance(item, tuple) else item
        
        # NEVER turn N64 primitives into opaque structs
        if tag in N64_PRIMITIVES or tag in SDK_DEFINES_THESE:
            continue
            
        if tag not in types_content:
            types_content += f"\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};"
            fixes += 1

    # 2. Fix Undeclared Identifiers
    for ident in categories["undeclared_idents"]:
        if ident in macros and f"#define {ident}" not in types_content:
            types_content += f"\n#define {ident} {macros[ident]}"
            fixes += 1

    # 3. Fix Incomplete Structs
    for tag in categories["need_struct_body"]:
        if tag in structs and tag not in types_content:
            types_content += f"\n{structs[tag]}"
            fixes += 1

    # 4. Fix Implicit Functions
    if categories["implicit_funcs"]:
        stubs = read_file(STUBS_FILE)
        for f in categories["implicit_funcs"]:
            if f"{f}()" not in stubs:
                stubs += f"\nlong long int {f}() {{ return 0; }}"
                fixes += 1
        write_file(STUBS_FILE, stubs)

    write_file(TYPES_HEADER, repair_unterminated_conditionals(types_content))
    return fixes

# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------
def main():
    intelligence_level = 1
    total_fixes = 0
    
    while intelligence_level <= 3:
        logger.info(f"\n[PHASE {intelligence_level}] Starting build cycle...")
        
        for attempt in range(5): # Increased attempts for complex fixes
            if run_build():
                logger.info("BUILD SUCCESSFUL!"); sys.exit(0)

            categories = {"missing_types": set(), "undeclared_idents": set(), 
                          "implicit_funcs": set(), "need_struct_body": set()}
            scrape_logs(categories)
            
            error_total = sum(len(v) for v in categories.values())
            if error_total == 0: 
                logger.warning("Build failed but no errors scraped. Advancing level...")
                break 
            
            applied = apply_fixes(categories, intelligence_level)
            total_fixes += applied
            if applied == 0: 
                logger.warning("No new fixes applied this cycle. Advancing level...")
                break
            
            logger.info(f"Cycle {attempt+1}: Applied {applied} fixes.")

        intelligence_level += 1

    logger.error("Could not resolve all build errors. Check Android/build_log.txt.")

if __name__ == "__main__":
    main()
