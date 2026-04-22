import os
import re
import logging
from collections import defaultdict
from typing import Dict, Set

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

# --- Paths ---
# Adjust these to match the exact paths in your development environment
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
CMAKE_LISTS_PATH = "Android/app/CMakeLists.txt"
BUILD_LOG_PATH = "full_build_log.txt"

# --- Constants & Protection Lists ---
# Protected globals that must be 'extern' and never #defined
_MACRO_SYNTHESIS_BLOCKLIST = {
    "__osPiTable", "__osFlashHandle", "__osSfHandle", 
    "__osCurrentThread", "__osRunQueue", "__osFaultedThread",
    "osTvType", "osClockRate", "osRomBase", "osResetType"
}

# Source-defined globals requiring extern declarations
_TYPED_SOURCE_GLOBAL_DECLS = {
    "__osPiTable": "extern struct OSPiHandle_s *__osPiTable;",
    "osTvType": "extern u32 osTvType;",
    "osClockRate": "extern u64 osClockRate;",
    "__osCurrentThread": "extern struct OSThread_s *__osCurrentThread;",
}

# Game-specific macros and constants found in logs
PHASE_3_MACROS = {
    "G_TEXTURE_IMAGE_FRAC": "2",
    "G_IM_SIZ_32b": "3",
    "G_TX_NOLOD": "0",
    "G_IM_FMT_RGBA": "0",
}

# Pre-defined structs needed by the game
ALL_STRUCTS = {
    "MapModelDescription": (
        "#ifndef RECOMP_MapModelDescription_DEFINED\n"
        "#define RECOMP_MapModelDescription_DEFINED\n"
        "typedef struct MapModelDescription_s {\n"
        "    int map_id;\n"
        "    int opa_model_id;\n"
        "    int xlu_model_id;\n"
        "    float scale;\n"
        "    long long int force_align_tail[60];\n"
        "} MapModelDescription;\n"
        "#endif"
    )
}

# Stubs for gs* macros to ensure they expand to valid constant expressions in C
_GS_MACRO_STUBS = """\
#ifndef RECOMP_GS_STUBS_DEFINED
#define RECOMP_GS_STUBS_DEFINED
#define gsDPPipeSync() {{0,0}}
#define gsDPTileSync() {{0,0}}
#define gsDPFullSync() {{0,0}}
#define gsDPLoadSync() {{0,0}}
#define rare_gDPLoadMultiBlock(...) {{0,0}}
#define rare_gDPLoadMultiBlock_4b(...) {{0,0}}
#endif /* RECOMP_GS_STUBS_DEFINED */
"""

# --- Utility logic for Linkage Errors ---
def normalize_path(filepath: str) -> str:
    """Removes leading project directories to ensure paths resolve reliably."""
    if ".." in filepath:
        filepath = os.path.normpath(filepath).replace('\\', '/')
    for marker in ["Banjo-recomp-android/", "Android/app/"]:
        if marker in filepath:
            return filepath.split(marker)[-1]
    return filepath.lstrip("/") if filepath.startswith("/") else filepath

def _scrub_linkage_comments(content: str) -> str:
    """Scrubs old auto-fixes so we don't duplicate comments on multiple runs."""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "AUTO-FIX LINKAGE:" in line:
            cleaned = line.replace("/* AUTO-FIX LINKAGE:", "").replace("/* AUTO-FIX LINKAGE: ", "").replace("// AUTO-FIX LINKAGE:", "").replace("*/", "").strip()
            lines[i] = cleaned
    return '\n'.join(lines)


# --- Core Logic ---
def _opaque_stub(tag: str, size: int = 64, missing_members: Set[str] = None) -> str:
    """Generates an aligned struct stub and synthesizes members extracted from the log."""
    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
    members = ""
    if missing_members:
        for m in sorted(missing_members):
            # Infer basic types from names (e.g., fX = float, count = int)
            type_str = "float" if m.startswith('f') else "int"
            members += f"    {type_str} {m};\n"
    
    return (
        f"#ifndef RECOMP_{tag}_DEFINED\n"
        f"#define RECOMP_{tag}_DEFINED\n"
        f"struct {struct_tag} {{\n"
        f"{members}"
        f"    long long int force_align[{size}];\n"
        f"}};\n"
        f"typedef struct {struct_tag} {tag};\n"
        f"#endif\n"
    )

def _scrape_logs_into_categories(categories: Dict) -> None:
    """Parses the provided log for specific error patterns and saves them to categories."""
    if not os.path.exists(BUILD_LOG_PATH): 
        logger.error(f"Could not find {BUILD_LOG_PATH}.")
        return

    content = open(BUILD_LOG_PATH, 'r').read()
    
    # 1. Find missing members in structs (e.g., 'unk4', 'count')
    for m in re.finditer(r"error: no member named '(\w+)' in '(?:struct\s+)?([a-zA-Z0-9_]+)'", content):
        member, struct_tag = m.groups()
        categories.setdefault("missing_members", defaultdict(set))[struct_tag].add(member)
        categories.setdefault("need_struct_body", set()).add(struct_tag)

    # 2. Find unknown type names (e.g., 'MapModelDescription')
    for m in re.finditer(r"error: unknown type name '([a-zA-Z0-9_]+)'", content):
        categories.setdefault("need_struct_body", set()).add(m.group(1))

    # 3. Find undeclared identifiers (e.g., missing macros)
    for m in re.finditer(r"error: use of undeclared identifier '([a-zA-Z0-9_]+)'", content):
        ident = m.group(1)
        if ident not in _MACRO_SYNTHESIS_BLOCKLIST:
            categories.setdefault("undeclared_vars", set()).add(ident)
            
    # 4. Find linkage conflicts
    for m in re.finditer(r"([^:]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+declaration of '(\w+)' has a different language linkage", content):
        file_err = normalize_path(m.group(1))
        func = m.group(2)
        categories.setdefault("linkage_conflict_files", set()).add((file_err, func))

def apply_fixes():
    """Main function to inject types, macros, and stubs based on logs."""
    categories = {}
    _scrape_logs_into_categories(categories)
    
    # Create n64_types.h if it doesn't exist
    if not os.path.exists(TYPES_HEADER):
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)
        with open(TYPES_HEADER, 'w') as f: f.write("#pragma once\n")

    content = open(TYPES_HEADER, 'r').read()
    
    # -- 1. Inject Macros and Variables --
    macro_injection = "\n// --- RECOMP_INJECT: MACROS ---\n"
    for m_name, m_val in PHASE_3_MACROS.items():
        macro_injection += f"#ifndef {m_name}\n#define {m_name} {m_val}\n#endif\n"
        
    for m_name in sorted(categories.get("undeclared_vars", set())):
        if m_name not in PHASE_3_MACROS:
            macro_injection += f"#ifndef {m_name}\n#define {m_name} 0\n#endif\n"
    macro_injection += "// --- END_RECOMP_INJECT: MACROS ---\n"
    
    # -- 2. Inject Graphics Macro Stubs --
    gs_stubs_injection = "\n// --- RECOMP_INJECT: GS_STUBS ---\n" + _GS_MACRO_STUBS + "// --- END_RECOMP_INJECT: GS_STUBS ---\n"
    
    # -- 3. Inject Missing Structs --
    struct_injection = "\n// --- RECOMP_INJECT: STRUCTS ---\n"
    for tag in categories.get("need_struct_body", set()):
        if tag in ALL_STRUCTS:
            struct_injection += ALL_STRUCTS[tag] + "\n"
        else:
            missing = categories.get("missing_members", {}).get(tag, set())
            struct_injection += _opaque_stub(tag, 64, missing)
    struct_injection += "// --- END_RECOMP_INJECT: STRUCTS ---\n"

    # -- 4. Inject Extern Declarations --
    extern_injection = "\n// --- RECOMP_INJECT: GLOBALS ---\n"
    for var, decl in _TYPED_SOURCE_GLOBAL_DECLS.items():
        extern_injection += f"#ifndef RECOMP_{var}_FWD\n{decl}\n#define RECOMP_{var}_FWD\n#endif\n"
    extern_injection += "// --- END_RECOMP_INJECT: GLOBALS ---\n"

    # Save to the central header
    with open(TYPES_HEADER, 'w') as f:
        f.write(content + macro_injection + gs_stubs_injection + struct_injection + extern_injection)
    
    # -- 5. Process Linkage Fixes in File Tree --
    if categories.get("linkage_conflict_files"):
        for filepath, func in categories["linkage_conflict_files"]:
            if os.path.exists(filepath):
                c = open(filepath, 'r').read()
                c = _scrub_linkage_comments(c)
                # Find the function declaration and comment it out
                pattern = rf"(?m)^(?![^\n]*// AUTO-FIX LINKAGE)(.*?\b{re.escape(func)}\s*\(.*?;)"
                c, n = re.subn(pattern, r"// AUTO-FIX LINKAGE: \1", c)
                if n > 0:
                    with open(filepath, 'w') as f: f.write(c)

    logger.info("Successfully patched project files based on build log analysis!")

if __name__ == "__main__":
    apply_fixes()
