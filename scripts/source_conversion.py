import os
import re
import logging
import sys
import subprocess
from collections import defaultdict, deque
from typing import Dict, Set, List, Tuple, Optional, Union
import yaml  # pip install pyyaml

# --- Configurable Paths ---
CONFIG = {
    "types_header": "Android/app/src/main/cpp/ultra/n64_types.h",
    "stubs_file": "Android/app/src/main/cpp/ultra/n64_stubs.c",
    "synth_internals": ["Android/app/src/main/cpp/../../../../../include/synthInternals.h", "include/synthInternals.h"],
    "build_log": "Android/full_build_log.txt",
    "build_command": "cd Android && ./gradlew assembleDebug",  # Adjust as needed
    "max_retries": 3,
    "log_fixes_to": "fixes_applied.log",
}

# Load from config.yaml if exists
if os.path.exists("config.yaml"):
    with open("config.yaml", "r") as f:
        CONFIG.update(yaml.safe_load(f))

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(CONFIG["log_fixes_to"]), logging.StreamHandler()],
)
logger = logging.getLogger("N64_RECOMP_ENGINE")

# --- Constants ---
TYPES_HEADER = CONFIG["types_header"]
STUBS_FILE = CONFIG["stubs_file"]
SYNTH_INTERNALS_H = CONFIG["synth_internals"][0]
SYNTH_INTERNALS_H_ALT = CONFIG["synth_internals"][1] if len(CONFIG["synth_internals"]) > 1 else None

# --- Error Patterns ---
ERROR_PATTERNS = {
    "linkage_conflict": re.compile(
        r"(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+error:\s+declaration of '(\w+)' has a different language linkage"
    ),
    "unknown_type": re.compile(r"error:\s+unknown type name '(\w+)'"),
    "incomplete_type": re.compile(r"error: member access into incomplete type '(?:struct|union )?(\w+)'"),
    "redefinition": re.compile(r"error:\s+redefinition of '(\w+)'"),
    "conflicting_types": re.compile(r"error:\s+conflicting types for '(\w+)'"),
    "implicit_declaration": re.compile(r"error:\s+implicit declaration of function '(\w+)'"),
    "undefined_reference": re.compile(r"error:\s+undefined reference to '(\w+)'"),
}

# --- Struct Dependencies (Manual Mapping) ---
# Maps structs to their dependencies (e.g., "OSThread" depends on "__OSThreadContext")
STRUCT_DEPENDENCIES = {
    "OSThread": ["__OSThreadContext", "OSMesgQueue"],
    "OSMesgQueue": ["OSThread"],
    "OSViMode": ["__OSViCommonRegs", "__OSViFieldRegs"],
    "OSTask": ["OSTask_t"],
    "Vtx": ["Vtx_t", "Vtx_n"],
    "Light": ["Light_t"],
    "Hilite": ["Hilite_t"],
}

# --- Existing Code (Keep ALL_STRUCTS, N64_PRIMITIVES, etc.) ---
# (Your existing dictionaries for ALL_STRUCTS, N64_PRIMITIVES, etc. remain unchanged)
# ...

# --- New: Topological Sort for Struct Injection Order ---
def topological_sort(nodes: Set[str], dependencies: Dict[str, List[str]]) -> List[str]:
    """Sort structs so dependencies are injected first."""
    in_degree = {node: 0 for node in nodes}
    graph = defaultdict(list)

    for node in nodes:
        for dep in dependencies.get(node, []):
            if dep in nodes:
                graph[dep].append(node)
                in_degree[node] += 1

    queue = deque([node for node in nodes if in_degree[node] == 0])
    sorted_nodes = []

    while queue:
        node = queue.popleft()
        sorted_nodes.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return sorted_nodes

# --- Enhanced Error Scraper ---
def _scrape_logs_into_categories(categories: dict) -> None:
    log_files = [CONFIG["build_log"], "full_build_log.txt", "build_log.txt", "Android/failed_files.log"]
    for log_file in log_files:
        if not os.path.exists(log_file):
            continue
        content = read_file(log_file)
        lines = content.split("\n")

        for i, line in enumerate(lines):
            for error_type, pattern in ERROR_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    symbol = match.group(1)
                    if error_type == "linkage_conflict":
                        file_err = normalize_path(match.group(1))
                        func = match.group(2)
                        file_note = None
                        for j in range(i + 1, min(i + 15, len(lines))):
                            m_note = re.search(
                                r"(/?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cpp|h)):\d+:\d+:\s+note:\s+previous declaration is here",
                                lines[j],
                            )
                            if m_note:
                                file_note = normalize_path(m_note.group(1))
                                break
                        if "sysroot" not in file_err and "ndk" not in file_err.lower():
                            categories.setdefault("linkage_conflict_files", set()).add((file_err, func))
                        elif file_note and "sysroot" not in file_note and "ndk" not in file_note.lower():
                            categories.setdefault("linkage_conflict_files", set()).add((file_note, func))
                    else:
                        categories.setdefault(error_type, set()).add(symbol)
                    break  # Only match one error per line

# --- New: Find Header Defining a Symbol ---
def find_header_for_symbol(symbol: str) -> Optional[str]:
    """Search for a header file that defines `symbol`."""
    search_dirs = ["include", "Android/app/src/main/cpp/ultra", "Android/app/src/main/cpp"]
    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue
        for root, _, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".h"):
                    path = os.path.join(root, file)
                    try:
                        content = read_file(path)
                        # Check for typedef or struct definition
                        if re.search(rf"\btypedef\s+(?:struct|union)\s+\w*\s+{{.*?}}\s+{re.escape(symbol)}\s*;", content):
                            return path
                        if re.search(rf"\bstruct\s+{re.escape(symbol)}(?:_s)?\s*{{", content):
                            return path
                    except Exception:
                        pass
    return None

# --- New: Add Missing Includes ---
def add_missing_includes(filepath: str, symbols: Set[str]) -> bool:
    """Add #include for headers defining missing symbols."""
    content = read_file(filepath)
    original = content
    includes_to_add = set()

    for symbol in symbols:
        header = find_header_for_symbol(symbol)
        if header and os.path.exists(header):
            rel_path = os.path.relpath(header, os.path.dirname(filepath))
            includes_to_add.add(f'#include "{rel_path}"')

    if includes_to_add:
        # Insert after existing includes or at the top
        include_block = "\n".join(sorted(includes_to_add)) + "\n\n"
        if "#include" in content:
            # Insert after the last #include
            last_include_idx = content.rfind("#include")
            newline_idx = content.find("\n", last_include_idx)
            content = content[:newline_idx + 1] + include_block + content[newline_idx + 1:]
        else:
            content = include_block + content

        if content != original:
            write_file(filepath, content)
            logger.info(f"Added includes to {filepath}: {includes_to_add}")
            return True
    return False

# --- Enhanced Fix Applier ---
def apply_fixes(categories: dict, intelligence_level: int = 3) -> Tuple[int, set]:
    fixes = 0
    fixed_files = set()

    heal_corrupted_headers()
    _scrape_logs_into_categories(categories)

    ensure_types_header_base(categories)

    if patch_synth_internals():
        fixes += 1
    if patch_exceptasm():
        fixes += 1

    # --- Struct Injection with Dependency Sorting ---
    target_tags = set(ALL_STRUCTS.keys())
    if "need_struct_body" in categories:
        target_tags |= categories["need_struct_body"]
    if "unknown_type" in categories:
        target_tags |= categories["unknown_type"]
    if "incomplete_type" in categories:
        target_tags |= categories["incomplete_type"]

    target_tags = {t for t in target_tags if t not in SDK_DEFINES_THESE and t not in N64_PRIMITIVES}

    # Sort structs by dependencies
    sorted_tags = topological_sort(target_tags, STRUCT_DEPENDENCIES)

    types_content = read_file(TYPES_HEADER)
    marker = "/* Forward declarations for source-defined typed globals */"
    if marker in types_content:
        types_content = types_content.split(marker)[0].strip()

    injected_structs = ""

    for tag in sorted_tags:
        if tag in target_tags:
            types_content = strip_redefinition(types_content, tag)
            if tag in ALL_STRUCTS:
                injected_structs += f"\n{ALL_STRUCTS[tag]}\n"
            elif tag in N64_OS_OPAQUE_TYPES:
                injected_structs += "\n" + _opaque_stub(tag)
            elif tag in N64_AUDIO_STATE_TYPES:
                injected_structs += f"\n#ifndef RECOMP_{tag}_DEFINED\n#define RECOMP_{tag}_DEFINED\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};\n#endif\n"
            target_tags.discard(tag)

    # --- Handle remaining tags ---
    for tag in list(target_tags):
        types_content = strip_redefinition(types_content, tag)
        if tag in ALL_STRUCTS:
            injected_structs += f"\n{ALL_STRUCTS[tag]}\n"
        elif tag in N64_OS_OPAQUE_TYPES:
            injected_structs += "\n" + _opaque_stub(tag)
        elif tag in N64_AUDIO_STATE_TYPES:
            injected_structs += f"\n#ifndef RECOMP_{tag}_DEFINED\n#define RECOMP_{tag}_DEFINED\ntypedef struct {tag}_s {{ long long int force_align[64]; }} {tag};\n#endif\n"

    # --- Inject into types header ---
    core_marker = "/* END_CORE_PRIMITIVES */"
    if core_marker in types_content:
        parts = types_content.split(core_marker, 1)
        types_content = parts[0] + core_marker + "\n" + injected_structs + parts[1]
    else:
        types_content = injected_structs + "\n" + types_content

    types_content += f"\n\n{marker}\n"
    types_content += "#ifndef RECOMP_OSViMode_fwd\n#define RECOMP_OSViMode_fwd\ntypedef struct OSViMode_s OSViMode;\n#endif\n"
    types_content += '#ifdef __cplusplus\nextern "C" {\n#endif\n'
    for var, decl in _TYPED_SOURCE_GLOBAL_DECLS.items():
        types_content += f"#ifndef RECOMP_{var}_fwd_DEFINED\n#define RECOMP_{var}_fwd_DEFINED\n{decl}\n#endif\n"
    types_content += '#ifdef __cplusplus\n}\n#endif\n'

    write_file(TYPES_HEADER, types_content)
    fixes += 1

    # --- Fix Linkage Conflicts ---
    if categories.get("linkage_conflict_files"):
        for filepath, func in categories["linkage_conflict_files"]:
            if os.path.exists(filepath):
                c = read_file(filepath)
                c = _scrub_linkage_comments(c)
                pattern = rf"(?m)^(?![^\n]*// AUTO-FIX LINKAGE)(.*?\b{re.escape(func)}\s*\(.*?;)"
                c, n = re.subn(pattern, r"// AUTO-FIX LINKAGE: \1", c)
                if n > 0:
                    if "#include <math.h>" not in c and func in _STDLIB_FUNCS:
                        c = "#include <math.h>\n" + c
                    write_file(filepath, c)
                    fixed_files.add(filepath)
                    fixes += 1

    # --- Fix Implicit Declarations (Generate Stub) ---
    if categories.get("implicit_declaration"):
        for func in categories["implicit_declaration"]:
            # Skip if already declared in stdlib
            if func in _STDLIB_FUNCS:
                continue
            # Add to stubs file
            stub = f"void {func}(void);  // AUTO-GENERATED STUB\n"
            if os.path.exists(STUBS_FILE):
                content = read_file(STUBS_FILE)
                if f"{func}(" not in content:
                    content += stub
                    write_file(STUBS_FILE, content)
                    fixes += 1
                    logger.info(f"Added stub for {func} to {STUBS_FILE}")

    # --- Fix Missing Includes ---
    if categories.get("unknown_type") or categories.get("incomplete_type"):
        all_missing_symbols = categories.get("unknown_type", set()) | categories.get("incomplete_type", set())
        for filepath, _ in categories.get("linkage_conflict_files", set()):
            if os.path.exists(filepath):
                if add_missing_includes(filepath, all_missing_symbols):
                    fixes += 1

    return fixes, fixed_files

# --- Build Retry Loop ---
def run_build() -> bool:
    """Run the build command and return True if successful."""
    try:
        result = subprocess.run(
            CONFIG["build_command"],
            shell=True,
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )
        logger.info(f"Build exit code: {result.returncode}")
        if result.stdout:
            logger.info("Build stdout:\n" + result.stdout[-1000:])  # Last 1000 chars
        if result.stderr:
            logger.error("Build stderr:\n" + result.stderr[-1000:])
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Build failed: {e}")
        return False

def main():
    retries = 0
    while retries < CONFIG["max_retries"]:
        logger.info(f"=== Build Attempt {retries + 1}/{CONFIG['max_retries']} ===")
        if run_build():
            logger.info("✅ Build succeeded!")
            return

        categories = {}
        fixes, fixed_files = apply_fixes(categories)
        if fixes == 0:
            logger.warning("No fixes applied. Build may have unrecoverable errors.")
            break

        logger.info(f"Applied {fixes} fixes to {len(fixed_files)} files: {fixed_files}")
        retries += 1

    logger.error("❌ Build failed after max retries.")

if __name__ == "__main__":
    main()