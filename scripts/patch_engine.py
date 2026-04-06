import os
import re
from collections import defaultdict

# These imports assume error_parser.py is present in the same directory
from error_parser import (
    BRACE_MATCH, N64_STRUCT_BODIES, KNOWN_MACROS,
    KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

# N64 audio DSP state types — inject opaque stubs so pointer-only uses compile.
N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE",
    "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
    "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

# Primitive names that must never be stubbed as structs.
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool",
    "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

# Registry for GBI types that need full definitions to avoid "incomplete type" errors.
# Using unions allows the code to access fields like gfx->words.w0 correctly.
GBI_STRUCT_DEFINITIONS = {
    "Gfx": "typedef union { struct { uint32_t w0; uint32_t w1; } words; long long int force_align; } Gfx;",
    "Vtx": "typedef union { struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } v; struct { short ob[3]; unsigned short flag; short tc[2]; signed char n[3]; unsigned char a; } n; } Vtx;",
    "Mtx": "typedef union { struct { int32_t m[4][4]; } m; struct { uint16_t int_part[4][4]; uint16_t frac_part[4][4]; } x; } Mtx;"
}

# ---------------------------------------------------------------------------
# Utility: Preamble stripping
# ---------------------------------------------------------------------------

def strip_auto_preamble(content):
    """Cleans up previously injected forward declarations to prevent bloat/conflicts."""
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
# Utility: Types-header bootstrap
# ---------------------------------------------------------------------------

def ensure_types_header_base():
    """Initializes n64_types.h ensuring primitives are defined before any includes."""
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        content = content.replace('#include "ultra/n64_types.h"\n', '')
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    # 1. Clean out existing primitive blocks to ensure a clean slate
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)

    primitive_types = ["u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
                       "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri"]
    for p in primitive_types:
        content = re.sub(rf"\btypedef\s+[^;]+\b{p}\s*;", "", content)

    # 2. Define the core primitives block
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

/* N64 SDK Primitive Aliases */
typedef u32 OSIntMask;
typedef u64 OSTime;
typedef u32 OSId;
typedef s32 OSPri;
typedef void* OSMesg;
#endif
"""
    # 3. Always insert primitives immediately after #pragma once to ensure priority over includes
    content = content.replace("#pragma once", f"#pragma once\n{core_primitives}", 1)
# ---------------------------------------------------------------------------
# Main fix dispatcher
# ---------------------------------------------------------------------------

def apply_fixes(categories):
    """Main entry point: applies fixes grouped by compiler error categories."""
    fixes       = 0
    fixed_files = set()
    injected_this_run = set()

    types_content = ensure_types_header_base()

    # 1. DYNAMIC CORRECTION: GBI Structural Integrity
    # Ensures core graphics types are unions to allow field access (e.g., .words.w0)
    for tag in ["Gfx", "Vtx", "Mtx"]:
        if tag in GBI_STRUCT_DEFINITIONS:
            if not re.search(rf"\b{tag}\b", types_content):
                types_content += f"\n/* AUTO: GBI Core Type */\n{GBI_STRUCT_DEFINITIONS[tag]}\n"
                injected_this_run.add(tag)
                write_file(TYPES_HEADER, types_content)
                fixes += 1

    # 2. Dynamic macro scrubber
    # Removes 0-stub macros if we've discovered the real type in the current pass
    known_types = set()
    for cat in ["missing_types", "need_struct_body", "incomplete_sizeof", "conflict_typedef"]:
        items = categories.get(cat, [])
        if not isinstance(items, (list, set, tuple)): 
            continue
        for item in items:
            tag = item[1] if isinstance(item, (list, tuple)) else item
            if isinstance(tag, str): 
                known_types.add(tag)

    for tag in known_types:
        p1 = rf"(?m)^\s*#ifndef {tag}\s*\n\s*#define {tag} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(p1, "", types_content)
        p2 = rf"(?m)^\s*#define {tag} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
        types_content, n2 = re.subn(p2, "", types_content)
        if n1 > 0 or n2 > 0:
            write_file(TYPES_HEADER, types_content); fixes += 1

    # 3. Dynamic missing members injection
    # Heuristically injects missing fields into structs based on usage patterns
    missing_m = categories.get("missing_members", [])
    if isinstance(missing_m, (list, set, tuple)):
        for item in sorted(missing_m):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            struct_name, member_name = item[0], item[1]
            types_content = read_file(TYPES_HEADER)
            pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"
            
            def inject_member(match, mn=member_name):
                body = match.group(2)
                if mn in body: return match.group(0)
                if any(x in mn.lower() for x in ["id", "label", "name", "buffer", "data", "str", "string"]):
                    return f"{match.group(1)}{body}    unsigned char {mn}[128]; /* AUTO-ARRAY */\n{match.group(3)}"
                if any(x in mn.lower() for x in ["ptr", "func", "cb", "handler"]):
                    return f"{match.group(1)}{body}    void* {mn}; /* AUTO-POINTER */\n{match.group(3)}"
                return f"{match.group(1)}{body}    long long int {mn};\n{match.group(3)}"

            if re.search(pattern, types_content):
                new_types, n = re.subn(pattern, inject_member, types_content)
                if n > 0:
                    write_file(TYPES_HEADER, new_types); types_content = new_types; fixes += 1
            else:
                types_content += f"\nstruct {struct_name} {{ long long int {member_name}; long long int force_align[64]; }};\n"
                write_file(TYPES_HEADER, types_content); fixes += 1

    # 4. DYNAMIC CORRECTION: Redefinition Scrubber (Source Cleaning)
    # Aggressively removes local definitions that clash with the global types header
    redef_items = categories.get("redefinition", [])
    if isinstance(redef_items, (list, set, tuple)):
        for item in sorted(redef_items):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            filepath, var = item[0], item[1]
            if os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                content = read_file(filepath)
                content, n1 = re.subn(rf"(?m)(?:typedef\s+)?struct\s+{var}\s*\{{({BRACE_MATCH})\}}\s*{var}?;?", f"/* AUTO-REMOVED STRUCT REDEF: {var} */", content)
                content, n2 = re.subn(rf"(?m)^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */", content)
                if n1 > 0 or n2 > 0:
                    if n1 > 0 and var not in types_content:
                        types_content += f"\ntypedef struct {var} {{ long long int force_align[64]; }} {var};\n"
                        write_file(TYPES_HEADER, types_content)
                    write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    # 5. Conflicting implicit-type prototypes
    # Resolves errors where functions are assumed to return 'int' but return pointers/64-bit values
    conflict_t = categories.get("conflicting_types", [])
    if isinstance(conflict_t, (list, set, tuple)):
        for item in sorted(conflict_t, key=str):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            filepath, func = item[0], item[1]
            if not os.path.exists(filepath): continue
            content = read_file(filepath)
            pattern = rf"(?:^|\n)([A-Za-z_][A-Za-z0-9_\s\*]+?)\s+\b{re.escape(func)}\s*\([^;{{]*\)\s*\{{"
            match = re.search(pattern, content)
            if match:
                sig_full = match.group(0)
                prototype = sig_full[:sig_full.rfind('{')].strip() + ";"
                if prototype not in content:
                    includes = list(re.finditer(r"#include\s+.*?\n", content))
                    injection = f"\n/* AUTO: resolve conflicting implicit type */\n{prototype}\n"
                    idx = includes[-1].end() if includes else 0
                    content = content[:idx] + injection + content[idx:]
                    write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    # 6. Incomplete sizeof handling
    # Provides dummy definitions for types used with sizeof() but not fully defined
    inc_sizeof = categories.get("incomplete_sizeof", [])
    if isinstance(inc_sizeof, (list, set, tuple)):
        types_content = read_file(TYPES_HEADER)
        added = False
        for item in inc_sizeof:
            tag = item[1] if isinstance(item, (list, tuple)) else item
            if isinstance(tag, str) and tag not in types_content and tag not in N64_STRUCT_BODIES:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                added = True
        if added: write_file(TYPES_HEADER, types_content); fixes += 1

    # 7. System Header Injection (Standard Library compatibility)
    # Satisfies implicit declarations for sinf, cosf, memcpy, etc.
    impl_func = categories.get("implicit_func", [])
    if isinstance(impl_func, (list, set, tuple)):
        h_map = {
            "sin": "<math.h>", "cos": "<math.h>", "sqrt": "<math.h>", 
            "abs": "<math.h>", "pow": "<math.h>", "round": "<math.h>",
            "memcpy": "<string.h>", "memset": "<string.h>", "strlen": "<string.h>",
            "malloc": "<stdlib.h>", "free": "<stdlib.h>", "exit": "<stdlib.h>"
        }
        types_content = read_file(TYPES_HEADER)
        added = False
        for func in impl_func:
            if not isinstance(func, str): continue
            for key, header in h_map.items():
                if key in func.lower() and header not in types_content:
                    types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                    added = True
        if added: write_file(TYPES_HEADER, types_content); fixes += 1
    # 8. Static / POSIX conflicts (Renaming)
    # Renames local static functions clashing with reserved Android/POSIX names
    seen_static = set()
    for cat in ["static_conflict", "posix_conflict", "posix_reserved_conflict"]:
        items = categories.get(cat, [])
        if not isinstance(items, (list, set, tuple)):
            continue
        for item in items:
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            filepath, func_name = item[0], item[1]
            if (filepath, func_name) in seen_static or not os.path.exists(filepath): continue
            seen_static.add((filepath, func_name))

            if filepath.endswith("n64_types.h"): continue

            content = read_file(filepath)
            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed: 
                    write_file(filepath, new_content)
                    fixed_files.add(filepath)
                    fixes += 1
            else:
                # General static conflict fix via filename-prefixed macro
                prefix = os.path.basename(filepath).split('.')[0]
                macro_fix = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
                if macro_fix not in content:
                    anchor = '#include "ultra/n64_types.h"'
                    if anchor in content:
                        content = content.replace(anchor, anchor + macro_fix)
                    else:
                        content = macro_fix + content
                    write_file(filepath, content)
                    fixed_files.add(filepath)
                    fixes += 1

    # 9. Actor pointer injection
    # Injects Actor instance pointer for functions using 'this' syntax
    actor_p = categories.get("actor_pointer", [])
    if isinstance(actor_p, (list, set, tuple)):
        for item in sorted(actor_p, key=str):
            filepath = item if isinstance(item, str) else str(item)
            if os.path.exists(filepath):
                content = original = read_file(filepath)
                if "Actor *actor =" not in content and "this" in content:
                    content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
                if content != original:
                    write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    # 10. Missing n64_types.h include verification (FIX FOR TypeError)
    # Checks every file mentioned in errors to ensure our compatibility header is present
    for cat in categories.keys():
        items = categories[cat]
        # Safety check: ensures the category value is iterable to prevent crashes
        if not isinstance(items, (list, set, tuple)):
            continue
        for item in items:
            filepath = item[0] if isinstance(item, (list, tuple)) else item
            if not isinstance(filepath, str) or not os.path.exists(filepath): continue
            if filepath.endswith(("n64_types.h", ".log", ".txt", ".json")): continue

            content = read_file(filepath)
            if 'include "ultra/n64_types.h"' not in content:
                header_inc = '#include "ultra/n64_types.h"\n'
                write_file(filepath, header_inc + content)
                fixed_files.add(filepath); fixes += 1

    # 11. Undeclared Macros and GBI Constants
    # Pulls missing N64 SDK constants from the known registry
    added = False
    types_content = read_file(TYPES_HEADER)
    all_idents = set()
    for cat in ["undeclared_macros", "undeclared_gbi", "undeclared_n64_types"]:
        items = categories.get(cat, [])
        if isinstance(items, (list, set, tuple)):
            for ident in items:
                if isinstance(ident, str): all_idents.add(ident)
    
    for ident in sorted(all_idents):
        if ident in KNOWN_FUNCTION_MACROS:
            defn = KNOWN_FUNCTION_MACROS[ident]
            if defn not in types_content:
                types_content += f"\n{defn}\n"; added = True
        elif ident in KNOWN_MACROS:
            if f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {KNOWN_MACROS[ident]}\n#endif\n"; added = True
        else:
            if f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* AUTO-INJECTED */\n#endif\n"; added = True
    if added: write_file(TYPES_HEADER, types_content); fixes += 1

    # 12. Undefined Linker Symbols -> generate SDK stubs
    # Satisfies implementations for SDK functions that haven't been ported yet
    symbols = categories.get("undefined_symbols", [])
    if isinstance(symbols, (list, set, tuple)) and symbols:
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED SDK STUBS */\n\n')
        existing_stubs = read_file(STUBS_FILE)
        stubs_added = False
        for sym in sorted(symbols):
            if not isinstance(sym, str) or sym.startswith("_Z") or "vtable" in sym: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"; stubs_added = True
        if stubs_added: write_file(STUBS_FILE, existing_stubs); fixes += 1

    # 13. SDK Struct bodies injection
    # Injects full structural definitions (e.g. OSThread) from the body registry
    struct_bodies = categories.get("need_struct_body", [])
    if isinstance(struct_bodies, (list, set, tuple)):
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(struct_bodies):
            if not isinstance(tag, str): continue
            body = N64_STRUCT_BODIES.get(tag)
            if body and not re.search(rf"\b{re.escape(tag)}\b", types_content):
                # Special cleanup for Mtx to avoid union conflicts
                if tag == "Mtx":
                    types_content = re.sub(rf"(?m)^typedef\s+union\s*\{{({BRACE_MATCH})\}}\s*__Mtx_data\s*;\n?", "", types_content)
                types_content += "\n" + body; bodies_added = True
        if bodies_added: write_file(TYPES_HEADER, types_content); fixes += 1

    return fixes, fixed_files

    write_file(TYPES_HEADER, content)
    return content

def _rename_posix_static(content, func_name, filepath):
    """Helper to rename static functions clashing with POSIX reserved names."""
    prefix   = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define   = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True
