import os
import re
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional, Union

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants and Config ---
TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# --- Imported Constants (Mock for demonstration) ---
BRACE_MATCH = r"[^{}]*"
N64_STRUCT_BODIES = {
    "Mtx": "typedef struct Mtx { float m[4][4]; } Mtx;",
    "LookAt": "typedef struct LookAt { float x, y, z; } LookAt;",
}
KNOWN_MACROS = {
    "OS_IM_1": "0x0001",
    "OS_IM_2": "0x0002",
}
KNOWN_FUNCTION_MACROS = {
    "SOME_FUNCTION_MACRO": "#define SOME_FUNCTION_MACRO(x) ((x) * 2)",
}
POSIX_RESERVED_NAMES = {"open", "close", "read", "write", "stat"}

# --- Helper Functions ---
def read_file(filepath: str) -> str:
    """Read content from a file."""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read {filepath}: {e}")
        return ""

def write_file(filepath: str, content: str) -> None:
    """Write content to a file."""
    try:
        with open(filepath, 'w') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write {filepath}: {e}")

def is_type_defined(tag: str, content: str) -> bool:
    """Check if a type is safely defined in the given C code content."""
    if f"typedef struct {tag}_s {tag};" in content: return True
    if f"typedef struct {tag} {tag};" in content: return True
    if re.search(rf"\}\s*{re.escape(tag)}\s*;", content): return True
    if re.search(rf"typedef\s+[^;]+?\b{re.escape(tag)}\s*;", content): return True
    return False

# --- Core Logic ---
def strip_auto_preamble(content: str) -> str:
    """Strip auto-generated preamble from content."""
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

def clean_conflicting_typedefs():
    """Remove all conflicting typedefs for N64 SDK types."""
    if not os.path.exists(TYPES_HEADER):
        return

    content = read_file(TYPES_HEADER)
    original_content = content

    # List of types that must NOT be redefined
    protected_types = ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]

    for p in protected_types:
        # Remove ALL typedefs for these types, regardless of their definition
        content = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s+{p}(?:_s)?\s*\{{[^}}]*\}}\s*{p}\s*;", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{p}\s*;", "", content)

    if content != original_content:
        write_file(TYPES_HEADER, content)

def ensure_types_header_base() -> str:
    """Ensure n64_types.h exists, cleans up bad macros, and injects primitives."""
    if os.path.exists(TYPES_HEADER):
        original_content = read_file(TYPES_HEADER)
        content = original_content
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        original_content = ""
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    # 1. Rip out the entire CORE_PRIMITIVES block so we can re-inject cleanly
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)

    # 2. Aggressively wipe out ANY loose primitive typedefs
    primitive_types = ["u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
                       "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]
    for p in primitive_types:
        content = re.sub(rf"\btypedef\s+[^;]+\b{p}\s*;", "", content)

    # 3. Scrub ALL conflicting typedefs for N64 SDK aliases (even if they are not primitives)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(rf"(?:typedef\s+)?(?:struct\s+)?{p}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{p}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{p}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{p}(?:_s)?\s+{p}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{p}(?:_s)?\s*;\n?", "", content)

    # 4. Reconstruct the core primitives block with ONLY the correct definitions
    core_primitives = """
#include <stdint.h>
#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
typedef uint8_t u8;
typedef int8_t s8;
typedef uint16_t u16;
typedef int16_t s16;
typedef uint32_t u32;
typedef int32_t s32;
typedef uint64_t u64;
typedef int64_t s64;
typedef float f32;
typedef double f64;
typedef int n64_bool;

/* N64 SDK Primitive Aliases (ONLY ONE DEFINITION PER TYPE) */
typedef u32 OSIntMask;
typedef u64 OSTime;
typedef u32 OSId;      /* MUST MATCH THE ORIGINAL SDK */
typedef s32 OSPri;     /* MUST MATCH THE ORIGINAL SDK */
typedef void* OSMesg;
#endif
"""
    # Replace only the FIRST #pragma once to prevent duplicate injections
    content = content.replace("#pragma once", f"#pragma once\n{core_primitives}", 1)

    if content != original_content:
        write_file(TYPES_HEADER, content)

    return content

def _rename_posix_static(content: str, func_name: str, filepath: str) -> Tuple[str, bool]:
    """Rename POSIX-reserved static functions."""
    prefix = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True

# --- Main Fix Dispatcher ---
def apply_fixes(categories: Dict[str, List]) -> Tuple[int, Set[str]]:
    """Apply all fixes based on the provided categories."""
    fixes = 0
    fixed_files = set()

    # --- NATIVE LOG SCRAPER: PREVENT DRIVER STALLS ---
    log_files = [
        "Android/failed_files.log", 
        "full_build_log.txt", 
        "build_log.txt", 
        "Android/build_log.txt"
    ]
    try:
        # Dynamically append any root logs if they exist
        for f in os.listdir("."):
            if f.endswith(".txt") or f.endswith(".log"):
                log_files.append(f)
    except Exception:
        pass

    for log_file in set(log_files):
        if not os.path.exists(log_file):
            continue
        content = read_file(log_file)
        
        # 1. Unknown type names with filepath (Self-Healing regex)
        for match in re.finditer(r"(?m)^(/[^\s:]+):\d+:\d+:\s+error:\s+unknown type name '(\w+)'", content):
            filepath, tag = match.groups()
            if "missing_types" not in categories: categories["missing_types"] = []
            if (filepath, tag) not in categories["missing_types"]:
                categories["missing_types"].append((filepath, tag))
        
        # 2. Catch-all without filepath
        for match in re.finditer(r"error:\s+unknown type name '(\w+)'", content):
            tag = match.group(1)
            if "missing_types" not in categories: categories["missing_types"] = []
            if not any(isinstance(x, (list, tuple)) and x[1] == tag for x in categories["missing_types"]):
                if tag not in categories["missing_types"]:
                    categories["missing_types"].append(tag)
    # -------------------------------------------------

    # FIRST: Clean up all conflicting typedefs
    clean_conflicting_typedefs()

    # THEN: Ensure the types header is properly initialized
    types_content = ensure_types_header_base()

    # --- Dynamic Macro Scrubber ---
    known_types = set()
    for item in categories.get("missing_types", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            known_types.add(item[1])
    for tag in categories.get("need_struct_body", []):
        if isinstance(tag, str): known_types.add(tag)
    for item in categories.get("incomplete_sizeof", []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            known_types.add(item[1])
    for tag in categories.get("conflict_typedef", []):
        if isinstance(tag, str): known_types.add(tag)

    macros_cleaned = False
    for tag in known_types:
        p1 = rf"(?m)^\s*#ifndef {tag}\s*\n\s*#define {tag} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(p1, "", types_content)
        p2 = rf"(?m)^\s*#define {tag} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
        types_content, n2 = re.subn(p2, "", types_content)
        if n1 > 0 or n2 > 0:
            macros_cleaned = True
            fixes += 1
    if macros_cleaned:
        write_file(TYPES_HEADER, types_content)

    # --- Dynamic Struct Redefinition Fixes ---
    for type_name in sorted(categories.get("conflict_typedef", [])):
        types_content = read_file(TYPES_HEADER)
        # Remove ALL definitions of this type, not just structs
        pattern = rf"(?:typedef\s+)?(?:struct\s+)?{type_name}\s*\{{[^}}]*\}}\s*{type_name}?\s*;\n?"
        new_types, n = re.subn(pattern, "", types_content)
        # Also remove any loose typedefs
        new_types = re.sub(rf"typedef\s+(?:u32|s32|u16|s16|u8|s8|u64|s64|int|unsigned\s+int|long|unsigned\s+long)\s+{type_name}\s*;", "", new_types)
        if n > 0:
            if f"struct {type_name}_s {{" not in new_types:
                new_types += f"\nstruct {type_name}_s {{ long long int force_align[64]; }};\n"
            write_file(TYPES_HEADER, new_types)
            types_content = new_types
            fixes += 1

    # --- Dynamic Missing Members Injection ---
    for item in sorted(categories.get("missing_members", [])):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        struct_name, member_name = item[0], item[1]
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"

        array_names = {"id", "label", "name", "buffer", "data", "str", "string", "temp"}

        def inject_member(match, mn=member_name, an=array_names):
            body = match.group(2)
            if mn not in body:
                if mn in an:
                    return f"{match.group(1)}{body}    unsigned char {mn}[128]; /* AUTO-ARRAY */\n{match.group(3)}"
                elif "ptr" in mn.lower() or "func" in mn.lower() or "cb" in mn.lower():
                    return f"{match.group(1)}{body}    void* {mn}; /* AUTO-POINTER */\n{match.group(3)}"
                else:
                    return f"{match.group(1)}{body}    long long int {mn};\n{match.group(3)}"
            return match.group(0)

        if re.search(pattern, types_content):
            new_types, n = re.subn(pattern, inject_member, types_content)
            if n > 0:
                write_file(TYPES_HEADER, new_types)
                types_content = new_types
                fixes += 1
        else:
            mn = member_name
            an = array_names
            if mn in an:
                injected_field = f"unsigned char {mn}[128]; /* AUTO-ARRAY */"
            elif "ptr" in mn.lower() or "func" in mn.lower() or "cb" in mn.lower():
                injected_field = f"void* {mn}; /* AUTO-POINTER */"
            else:
                injected_field = f"long long int {mn};"
            types_content += f"\nstruct {struct_name} {{\n    {injected_field}\n    long long int force_align[64];\n}};\n"
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Variable Redefinition Fixes ---
    for item in sorted(categories.get("redefinition", [])):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        filepath, var = item[0], item[1]
        if os.path.exists(filepath):
            content = read_file(filepath)
            new_content, n = re.subn(
                rf"^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */",
                content, flags=re.MULTILINE)
            if n > 0:
                write_file(filepath, new_content)
                fixed_files.add(filepath)
                fixes += 1

    # --- Missing Types → Opaque Stubs ---
    N64_PRIMITIVES = {
        "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
        "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
    }
    N64_AUDIO_STATE_TYPES = {
        "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
        "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
        "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
    }

    for item in sorted(categories.get("missing_types", []), key=str):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            filepath, tag = item[0], item[1]
        else:
            filepath, tag = None, item

        if not isinstance(tag, str):
            continue

        types_content = read_file(TYPES_HEADER)

        if tag in N64_PRIMITIVES:
            continue
        if tag in N64_AUDIO_STATE_TYPES:
            if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                write_file(TYPES_HEADER, types_content)
                fixes += 1
            continue

        if tag in N64_STRUCT_BODIES:
            categories.setdefault("need_struct_body", set()).add(tag)
        else:
            if tag in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
                continue
            struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
            decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
            
            # Robust duplicate guard
            if not is_type_defined(tag, types_content):
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content)
                fixed_files.add(TYPES_HEADER)
                fixes += 1

        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            # More relaxed include check
            if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                fixed_files.add(filepath)
                fixes += 1

    # --- Explicit Unknown Audio State Types ---
    if categories.get("unknown_audio_state_types"):
        types_content = read_file(TYPES_HEADER)
        added = False
        for t in sorted(categories["unknown_audio_state_types"]):
            if not isinstance(t, str) or t not in N64_AUDIO_STATE_TYPES:
                continue
            if f"typedef struct {t}" not in types_content and f"}} {t};" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
                added = True
        if added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Extraneous Brace Cleanup ---
    if categories.get("extraneous_brace"):
        types_content = read_file(TYPES_HEADER)
        original = types_content
        types_content = re.sub(
            r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n",
            "", types_content)
        types_content = re.sub(
            r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{",
            r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Conflicting Implicit-Type Prototypes ---
    for item in sorted(categories.get("conflicting_types", []), key=str):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            filepath, func = item[0], item[1]
        else:
            continue
        if not os.path.exists(filepath):
            continue
        content = read_file(filepath)
        pattern = rf"(?:^|\n)([A-Za-z_][A-Za-z0-9_\s\*]+?)\s+\b{re.escape(func)}\s*\([^;{{]*\)\s*\{{"
        match = re.search(pattern, content)
        if match:
            sig_full = match.group(0)
            prototype = sig_full[:sig_full.rfind('{')].strip() + ";"
            if prototype not in content:
                includes = list(re.finditer(r"#include\s+.*?\n", content))
                injection = f"\n/* AUTO: resolve conflicting implicit type */\n{prototype}\n"
                if includes:
                    idx = includes[-1].end()
                    content = content[:idx] + injection + content[idx:]
                else:
                    content = injection + content
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # --- Missing n64_types.h Include ---
    for item in sorted(categories.get("missing_n64_types", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        if 'n64_types.h"' not in content and '<n64_types.h>' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath)
            fixes += 1

    # --- Actor Pointer Injection ---
    for item in sorted(categories.get("actor_pointer", []), key=str):
        filepath = item if isinstance(item, str) else str(item)
        if not os.path.exists(filepath):
            continue
        content = original = read_file(filepath)
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # --- Local Struct Forward Declarations ---
    if categories.get("local_struct_fwd"):
        file_to_types = defaultdict(set)
        for item in categories["local_struct_fwd"]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                file_to_types[item[0]].add(item[1])
        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
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
                fixed_files.add(filepath)
                fixes += 1

    # --- Typedef / Struct Redefinitions ---
    fixd_files = set()
    for item in categories.get("typedef_redef", []):
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            fixd_files.add(item[0])
    for item in categories.get("struct_redef", []):
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            fixd_files.add(item[0])

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
            continue
        content = read_file(filepath)
        original = content
        content = strip_auto_preamble(content)

        tagged_body_re = re.compile(
            rf'(?:typedef\s+)?struct\s+(\w+)\s*\{{[^}}]*\}}\s*[^;]*;', re.DOTALL)
        tag_matches = defaultdict(list)
        for m in tagged_body_re.finditer(content):
            tag_matches[m.group(1)].append(m)
        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]):
                    content = content[:m.start()] + content[m.end():]

        for item in categories.get("typedef_redef", []):
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            fp2, type1, type2 = item[0], item[1], item[2]
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

            # 1. Rename anonymous structs defining the alias
            anon_pat = rf"typedef\s+struct\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_pat, content):
                def _anon_sub(m):
                    return f"typedef struct {target_tag} {{{m.group(1)}}} {m.group(2)};"
                content, _ = re.subn(anon_pat, _anon_sub, content)

            # 2. Rename explicitly named structs that improperly use the alias as their tag
            bad_named_pat = rf"(?:typedef\s+)?struct\s+{re.escape(alias)}\s*\{{([^}}]*)\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(bad_named_pat, content):
                def _bad_named_sub(m):
                    return f"typedef struct {target_tag} {{{m.group(1)}}} {m.group(2)};"
                content, _ = re.subn(bad_named_pat, _bad_named_sub, content)

            # 3. Replace remaining occurrences of `struct alias` with `struct target_tag`
            content, _ = re.subn(
                r"\bstruct\s+" + re.escape(alias) + r"\b",
                f"struct {target_tag}", content)


        for item in categories.get("struct_redef", []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            fp2, tag = item[0], item[1]
            if fp2 != filepath:
                continue
            content, _ = re.subn(
                rf'struct\s+{re.escape(tag)}\s*\{{[^}}]*\}}\s*;\n?', "", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    # --- Incomplete Sizeof ---
    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen = set()
        for item in categories["incomplete_sizeof"]:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            filepath, tag = item[0], item[1]
            if tag in seen:
                continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES:
                continue
            is_sdk = (tag.isupper() or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_"))
                      or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Static / POSIX Conflicts ---
    seen_static = set()
    for cat in ["static_conflict", "posix_conflict", "posix_reserved_conflict"]:
        for item in categories.get(cat, []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            filepath, func_name = item[0], item[1]
            key = (filepath, func_name)
            if key in seen_static:
                continue
            seen_static.add(key)
            if not func_name or not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
                continue
            content = read_file(filepath)

            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath)
                    fixes += 1
                continue

            prefix = os.path.basename(filepath).split('.')[0]
            macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
            if macro_fix not in content:
                anchor = '#include "ultra/n64_types.h"'
                content = (content.replace(anchor, anchor + macro_fix)
                           if anchor in content else macro_fix + content)
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # --- Undeclared Macros ---
    if categories.get("undeclared_macros"):
        types_content = read_file(TYPES_HEADER)
        macros_added = False
        for macro in sorted(categories["undeclared_macros"]):
            if not isinstance(macro, str):
                continue
            if macro in KNOWN_FUNCTION_MACROS:
                defn = KNOWN_FUNCTION_MACROS[macro]
                if defn not in types_content:
                    types_content += f"\n{defn}\n"
                    macros_added = True
            elif macro in KNOWN_MACROS:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {KNOWN_MACROS[macro]}\n#endif\n"
                    macros_added = True
            else:
                if f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Implicit Function Declarations → System Headers ---
    if categories.get("implicit_func"):
        math_funcs = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        types_content = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if not isinstance(func, str):
                continue
            if func in math_funcs:
                header = "<math.h>"
            elif func in string_funcs:
                header = "<string.h>"
            elif func in stdlib_funcs:
                header = "<stdlib.h>"
            else:
                continue
            if f"#include {header}" not in types_content:
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Undefined Linker Symbols → Stubs ---
    if categories.get("undefined_symbols"):
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace(
                        "add_library(", "add_library(\n        ultra/n64_stubs.c")
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added = False
        for sym in sorted(categories["undefined_symbols"]):
            if not isinstance(sym, str):
                continue
            if sym.startswith("_Z") or "vtable" in sym:
                continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    # --- Audio-State Opaque Types ---
    if categories.get("audio_states"):
        types_content = read_file(TYPES_HEADER)
        audio_added = False
        for t in sorted(categories["audio_states"]):
            if not isinstance(t, str):
                continue
            if f"typedef struct {t}" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Undeclared N64 Platform Types ---
    if categories.get("undeclared_n64_types"):
        types_content = read_file(TYPES_HEADER)
        k_added = False
        
        for item in sorted(categories["undeclared_n64_types"], key=str):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                filepath, t = item[0], item[1]
            elif isinstance(item, str):
                filepath, t = None, item
            else:
                continue

            if not isinstance(t, str):
                continue

            if t in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
                pass
            else:
                struct_tag = f"{t}_s" if not t.endswith("_s") else t
                decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {t};\n"
                
                # Robust duplicate guard
                if not is_type_defined(t, types_content):
                    types_content += f"\n#ifndef {t}_DEFINED\n#define {t}_DEFINED\n{decl}#endif\n"
                    k_added = True

            if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                c = read_file(filepath)
                # More relaxed include check
                if 'n64_types.h"' not in c and '<n64_types.h>' not in c:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                    fixed_files.add(filepath)
                    fixes += 1

        if k_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1
            fixed_files.add(TYPES_HEADER)

        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs)
                fixes += 1


    # --- Undeclared GBI Constants ---
    if categories.get("undeclared_gbi"):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if not isinstance(ident, str):
                continue
            if ident in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {KNOWN_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                gbi_added = True
        if gbi_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Full Struct Bodies for Known N64 Types ---
    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(categories["need_struct_body"]):
            if not isinstance(tag, str):
                continue
            body = N64_STRUCT_BODIES.get(tag)
            if not body:
                continue
            already = (re.search(rf"\}}\s*{re.escape(tag)}\s*;", types_content) or
                      re.search(rf"typedef\s+struct\s+{re.escape(tag)}\b", types_content))
            if already:
                continue
            if tag == "LookAt":
                types_content = re.sub(
                    rf"(?m)^typedef\s+struct\s*\{{[^}}]*\}}\s*__Light_t\s*;\n?", "", types_content)
                types_content = re.sub(
                    rf"(?m)^typedef\s+struct\s*\{{[^}}]*\}}\s*__LookAtDir\s*;\n?", "", types_content)
            if tag == "Mtx":
                types_content = re.sub(
                    rf"(?m)^typedef\s+union\s*\{{[^}}]*\}}\s*__Mtx_data\s*;\n?", "", types_content)
            types_content = re.sub(
                rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{[^}}]*\}}\s*(?:{re.escape(tag)}\s*)?;?\n?",
                "", types_content)
            types_content = re.sub(
                rf"typedef\s+struct\s*\{{[^}}]*\}}\s*{re.escape(tag)}\s*;\n?", "", types_content)
            types_content = re.sub(
                rf"typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;\n?", "", types_content)
            types_content = re.sub(
                rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
            types_content += "\n" + body
            bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- Local Forward-Only Declarations ---
    if categories.get("local_fwd_only"):
        file_to_types = defaultdict(set)
        for item in categories["local_fwd_only"]:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                file_to_types[item[0]].add(item[1])

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"):
                continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{[^}}]*\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
                if re.search(body_pattern, content):
                    fwd = f"/* AUTO: forward decl for type defined below */\ntypedef struct {t}_s {t};\n"
                    if f"typedef struct {t}_s {t};" not in content:
                        content = fwd + content
                        changed = True
                else:
                    fwd = f"/* AUTO: forward declarations */\ntypedef struct {t}_s {t};\n"
                    if f"typedef struct {t}_s {t};" not in content:
                        content = fwd + content
                        changed = True
            if changed:
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    # --- Missing Global Extern Declarations ---
    if categories.get("missing_globals"):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for item in sorted(categories["missing_globals"], key=str):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                _, glob = item[0], item[1]
            elif isinstance(item, str):
                glob = item
            else:
                continue
            if glob == "actor":
                continue
            if (f" {glob};" not in types_content and f"*{glob};" not in types_content
                    and f" {glob}[" not in types_content):
                decl = (f"extern void* {glob};" if glob.endswith(("_ptr", "_p"))
                        else f"extern long long int {glob};")
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    return fixes, fixed_files
