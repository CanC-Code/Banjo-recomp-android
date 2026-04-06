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

# Registry for types that need opaque stubs to compile (Restored for Audio recovery)
N64_AUDIO_STATE_TYPES = {
    "RESAMPLE_STATE", "POLEF_STATE", "ENVMIX_STATE", "ADPCM_STATE",
    "INTERLEAVE_STATE", "ENVMIX_STATE2", "HIPASSLOOP_STATE",
    "COMPRESS_STATE", "REVERB_STATE", "MIXER_STATE",
}

# Fundamental primitives (Added Acmd to fix File 4 error)
N64_PRIMITIVES = {
    "u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64",
    "f32", "f64", "n64_bool", "Acmd",
    "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg",
}

# Registry for GBI types that need full Union definitions for field access (.words.w0)
GBI_STRUCT_DEFINITIONS = {
    "Gfx": "typedef union { struct { uint32_t w0; uint32_t w1; } words; long long int force_align; } Gfx;",
    "Vtx": "typedef union { struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } v; struct { short ob[3]; unsigned short flag; short tc[2]; signed char n[3]; unsigned char a; } n; } Vtx;",
    "Mtx": "typedef union { struct { int32_t m[4][4]; } m; struct { uint16_t int_part[4][4]; uint16_t frac_part[4][4]; } x; } Mtx;"
}

# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def strip_auto_preamble(content):
    """Cleans up previously injected forward declarations to prevent bloat."""
    if not content: return ""
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

def ensure_types_header_base():
    """
    Initializes n64_types.h with primitives. 
    Fixes the 'f32' error by moving System headers UP and SDK headers DOWN.
    """
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER) or ""
        if "#pragma once" not in content: content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    # 1. Aggressive primitive cleanup
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)
    
    # 2. Extract and sort includes to prevent circular dependency errors
    all_includes = re.findall(r'^#include\s+.*?\n', content, flags=re.MULTILINE)
    content = re.sub(r'^#include\s+.*?\n', '', content, flags=re.MULTILINE)

    system_incs = [i for i in all_includes if "<" in i] # e.g. <math.h>
    sdk_incs    = [i for i in all_includes if '"' in i] # e.g. "PR/libaudio.h"

    # 3. Inject the core types (Adding Acmd as u64 is the primary fix for the current stall)
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
typedef u64 Acmd; 

/* N64 SDK Primitive Aliases */
typedef u32 OSIntMask;
typedef u64 OSTime;
typedef u32 OSId;
typedef s32 OSPri;
typedef void* OSMesg;
#endif
"""
    # 4. Reconstruct: Primitives -> System Headers -> Body -> SDK Headers (Bottom)
    content = content.replace("#pragma once", "#pragma once\n" + core_primitives, 1)
    
    if system_incs:
        content = content.replace("#endif", "#endif\n" + "".join(sorted(set(system_incs))), 1)
    
    if sdk_incs:
        # Move SDK headers to the very end so they can 'see' our stubs/unions
        content = content.rstrip() + "\n\n/* SDK Headers (deferred to bottom to see stubs) */\n" + "".join(sorted(set(sdk_incs)))

    write_file(TYPES_HEADER, content)
    return content

def _rename_posix_static(content, func_name, filepath):
    """Helper to rename static functions clashing with Android/POSIX names."""
    prefix   = os.path.basename(filepath).split('.')[0]
    new_name = f"n64_{prefix}_{func_name}"
    define   = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content: return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True
# ---------------------------------------------------------------------------
# Main Fix Dispatcher - Section 2
# ---------------------------------------------------------------------------

def apply_fixes(categories):
    """
    Main entry point for the patch engine. Processes parsed error categories 
    and applies surgical fixes to n64_types.h and individual source files.
    """
    fixes = 0
    fixed_files = set()
    
    # 1. SMART HEADER INITIALIZATION
    # Retrieves the current content of n64_types.h with the correct primitive 
    # and include ordering established in Section 1.
    types_content = ensure_types_header_base() or ""

    # ------------------------------------------------------------------
    # 2. GBI STRUCTURAL INTEGRITY (Union Injection)
    # ------------------------------------------------------------------
    # The Nintendo 64 Graphics Binary Interface (GBI) relies on specific 
    # memory layouts for commands (Gfx) and matrices (Mtx). By defining 
    # these as unions, we allow the recompilation to use bit-field accessors 
    # (like g->words.w0) which is standard in High-Level Emulation (HLE).
    # ------------------------------------------------------------------
    
    
    
    for tag in ["Gfx", "Vtx", "Mtx"]:
        if tag in GBI_STRUCT_DEFINITIONS:
            # Prevent duplicate definitions by checking word-boundary presence
            if not re.search(rf"\b{tag}\b", types_content):
                types_content += f"\n/* AUTO: GBI Core Union - Required for .words and .v access */\n{GBI_STRUCT_DEFINITIONS[tag]}\n"
                write_file(TYPES_HEADER, types_content)
                fixes += 1

    # ------------------------------------------------------------------
    # 3. UNIVERSAL OPAQUE STUBBER (The "File 380" Safety Net)
    # ------------------------------------------------------------------
    # This logic is the primary engine for bypassing "unknown type name" 
    # errors. Instead of requiring a manual definition for every N64 struct, 
    # we automatically generate structural stubs (opaque structs).
    #
    # This allows the compiler to treat the name as a valid type for 
    # pointers and function signatures, which is sufficient for most 
    # recompilation tasks and allows the build to progress through hundreds 
    # of files without stalling.
    # ------------------------------------------------------------------
    
    missing_t = categories.get("missing_types", [])
    
    # Resilience check: Ensure we are iterating over a sequence to avoid TypeError crashes
    if isinstance(missing_t, (list, set, tuple)):
        added_stub = False
        
        # Sort items to ensure n64_types.h remains deterministic across runs
        for item in sorted(missing_t, key=str):
            # Parse the tag from either a direct string or a (file, tag) metadata tuple
            tag = item[1] if isinstance(item, (list, tuple)) and len(item) >= 2 else item
            
            # Filter out primitives and non-string entries
            if not isinstance(tag, str) or tag in N64_PRIMITIVES: 
                continue
            
            # Check if a definition already exists in the header to prevent 'redefinition' errors
            if f"struct {tag}" not in types_content and f" {tag};" not in types_content:
                
                # Audio states (ADPCM_STATE, etc.) are treated with a specialized 
                # typedef to maintain compatibility with libaudio.h.
                if tag in N64_AUDIO_STATE_TYPES:
                    decl = f"typedef struct {tag} {{ long long int force_align[64]; }} {tag};"
                else:
                    # Standard engine types use the IDO-style struct_s naming convention
                    struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
                    decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};"
                
                # Injection with #ifndef guards ensures the patch is atomic and idempotent
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}\n#endif\n"
                added_stub = True
        
        if added_stub:
            write_file(TYPES_HEADER, types_content)
            fixes += 1
    # ------------------------------------------------------------------
    # 4. DYNAMIC MISSING MEMBERS INJECTION
    # ------------------------------------------------------------------
    # This logic handles cases where the recompilation code accesses a 
    # member of a struct that was defined as an opaque stub. It 
    # dynamically injects the missing field into n64_types.h using 
    # regex and heuristics to guess the correct data type.
    # ------------------------------------------------------------------
    missing_m = categories.get("missing_members", [])
    if isinstance(missing_m, (list, set, tuple)):
        # Keywords suggesting a member should be an array (buffer)
        array_names = {"id", "label", "name", "buffer", "data", "str", "string", "temp"}
        
        for item in sorted(missing_m):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            struct_name, member_name = item[0], item[1]
            
            # Refresh types_content to handle sequential injections correctly
            types_content = read_file(TYPES_HEADER) or ""
            pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"

            def inject_member(match, mn=member_name, an=array_names):
                body = match.group(2)
                if mn in body: return match.group(0) # Member already injected
                
                # Heuristic: Decide type based on member naming convention
                if mn in an or any(x in mn.lower() for x in ["buf", "data", "name"]):
                    return f"{match.group(1)}{body}    unsigned char {mn}[128]; /* AUTO-ARRAY */\n{match.group(3)}"
                if any(x in mn.lower() for x in ["ptr", "func", "cb", "handler"]):
                    return f"{match.group(1)}{body}    void* {mn}; /* AUTO-POINTER */\n{match.group(3)}"
                
                # Default to long long int to preserve 64-bit alignment/padding
                return f"{match.group(1)}{body}    long long int {mn}; /* AUTO-MEMBER */\n{match.group(3)}"

            if re.search(pattern, types_content):
                new_types, n = re.subn(pattern, inject_member, types_content)
                if n > 0:
                    write_file(TYPES_HEADER, new_types)
                    types_content = new_types
                    fixes += 1
            else:
                # Fallback: Create the struct if it was somehow missing entirely
                types_content += f"\nstruct {struct_name} {{ long long int {member_name}; long long int force_align[64]; }};\n"
                write_file(TYPES_HEADER, types_content)
                fixes += 1

    # ------------------------------------------------------------------
    # 5. REDEFINITION SCRUBBER (Aggressive Local Cleaning)
    # ------------------------------------------------------------------
    # Resolves 'redefinition of...' errors by locating the offending local 
    # definition in .c/.cpp files and commenting it out. This ensures 
    # n64_types.h remains the single source of truth for the project.
    # ------------------------------------------------------------------
    redef_items = categories.get("redefinition", [])
    if isinstance(redef_items, (list, set, tuple)):
        for item in sorted(redef_items):
            if not isinstance(item, (list, tuple)) or len(item) < 2: continue
            filepath, var = item[0], item[1]
            
            # Never scrub the master compatibility header itself
            if os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                content = read_file(filepath) or ""
                # Comment out variable/typedef definitions while preserving context
                content, n = re.subn(rf"(?m)^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */", content)
                if n > 0:
                    write_file(filepath, content)
                    fixed_files.add(filepath)
                    fixes += 1

    # ------------------------------------------------------------------
    # 6. IMPLICIT FUNCTION HEADERS (Standard Library Injection)
    # ------------------------------------------------------------------
    # Many legacy N64 functions assume implicit declarations of math or 
    # string utilities. This block injects missing standard headers.
    # ------------------------------------------------------------------
    impl_func = categories.get("implicit_func", [])
    if isinstance(impl_func, (list, set, tuple)):
        # Map common symbols to their modern standard headers
        h_map = {
            "sin": "<math.h>", "cos": "<math.h>", "sqrt": "<math.h>", 
            "memcpy": "<string.h>", "memset": "<string.h>", "strlen": "<string.h>",
            "malloc": "<stdlib.h>", "free": "<stdlib.h>", "atoi": "<stdlib.h>"
        }
        
        types_content = read_file(TYPES_HEADER) or ""
        added_h = False
        for func in impl_func:
            if not isinstance(func, str): continue
            for key, header in h_map.items():
                if key in func.lower() and header not in types_content:
                    # Place standard headers immediately after #pragma once
                    types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                    added_h = True
        if added_h:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # ------------------------------------------------------------------
    # 7. ACTOR POINTER INJECTION (Bridge for Recompilation Context)
    # ------------------------------------------------------------------
    # In Banjo-recomp, functions often exist within a C++ class but 
    # the original logic expects a global 'Actor' pointer. This surgical 
    # fix injects a local pointer into functions that utilize 'this'.
    # ------------------------------------------------------------------
    actor_p = categories.get("actor_pointer", [])
    if isinstance(actor_p, (list, set, tuple)):
        for item in sorted(actor_p, key=str):
            filepath = item if isinstance(item, str) else str(item)
            if os.path.exists(filepath):
                content = read_file(filepath) or ""
                # Inject only if 'this' exists but 'actor' hasn't been set up yet
                if "Actor *actor =" not in content and "this" in content:
                    content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
                    write_file(filepath, content)
                    fixed_files.add(filepath)
                    fixes += 1
    # ------------------------------------------------------------------
    # 8. HEADER INCLUSION VERIFICATION (The Global Safety Net)
    # ------------------------------------------------------------------
    # This logic iterates through every error reported by the compiler. 
    # If a file is failing, it almost certainly requires n64_types.h 
    # to resolve primitive and macro conflicts. We prepend the include 
    # to ensure it is the first thing the preprocessor sees.
    # ------------------------------------------------------------------
    for cat in categories.keys():
        items = categories[cat]
        if not isinstance(items, (list, set, tuple)): continue
        for item in items:
            # Extract the filename regardless of whether the error is a tuple or string
            filepath = item[0] if isinstance(item, (list, tuple)) else item
            
            # Skip non-source files or the header itself to avoid infinite recursion
            if (isinstance(filepath, str) and os.path.exists(filepath) and 
                not filepath.endswith(("h", "log", "txt", "json"))):
                
                content = read_file(filepath) or ""
                if 'include "ultra/n64_types.h"' not in content:
                    # Prepend the include at the very top of the file
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
                    fixed_files.add(filepath)
                    fixes += 1

    # ------------------------------------------------------------------
    # 9. LINKER STUB GENERATION (Satisfying the NDK Linker)
    # ------------------------------------------------------------------
    # When the compiler finishes, the linker searches for function 
    # definitions. Missing N64 SDK functions (like osSetIntMask) will 
    # cause the build to fail. We generate a C file containing 
    # "empty" versions of these functions to satisfy the requirement.
    # ------------------------------------------------------------------
    symbols = categories.get("undefined_symbols", [])
    if isinstance(symbols, (list, set, tuple)) and symbols:
        # Initialize the stubs file with our header for type consistency
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED SDK STUBS */\n\n')
        
        existing_stubs = read_file(STUBS_FILE) or ""
        stubs_added = False
        
        for sym in sorted(symbols):
            # Ignore mangled C++ symbols (starting with _Z) or vtables
            if not isinstance(sym, str) or sym.startswith("_Z") or "vtable" in sym: 
                continue
            
            # Check if this function is already stubbed to prevent duplication
            if f" {sym}(" not in existing_stubs:
                # Stub with 64-bit return type for maximum architectural safety
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
                
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    # ------------------------------------------------------------------
    # 10. FULL SDK STRUCT INJECTION (High-Fidelity Replacement)
    # ------------------------------------------------------------------
    # Some N64 types (like LookAt or Hilite) are used in code that 
    # requires knowledge of their internal members. This block identifies 
    # when we've used an opaque stub but actually need the real struct 
    # definition from error_parser.N64_STRUCT_BODIES.
    # ------------------------------------------------------------------
    struct_bodies = categories.get("need_struct_body", [])
    if isinstance(struct_bodies, (list, set, tuple)):
        # Re-read to ensure we have the absolute latest state of the header
        types_content = read_file(TYPES_HEADER) or ""
        bodies_added = False
        
        for tag in sorted(struct_bodies):
            if not isinstance(tag, str): continue
            body = N64_STRUCT_BODIES.get(tag)
            
            # If we have a real definition for this tag and haven't injected it yet
            if body and not re.search(rf"\b{re.escape(tag)}\b.*\{{", types_content):
                # Aggressively remove any existing opaque stubs/macros for this type
                types_content = re.sub(rf"(?m)^#ifndef {tag}_DEFINED\n[\s\S]*?^#endif\n?", "", types_content)
                types_content = re.sub(rf"(?m)^(typedef\s+)?struct\s+{tag}_s\s*\{{[^}}]*\}}[^;]*;", "", types_content)
                
                # Cleanup specific GBI naming conflicts before injection
                if tag == "LookAt":
                    types_content = re.sub(rf"(?m)^typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*__(?:Light_t|LookAtDir)\s*;\n?", "", types_content)
                elif tag == "Mtx":
                    types_content = re.sub(rf"(?m)^typedef\s+union\s*\{{({BRACE_MATCH})\}}\s*__Mtx_data\s*;\n?", "", types_content)

                # Inject the real structural body
                types_content += "\n" + body
                bodies_added = True
        
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # Return summary to the build driver
    return fixes, fixed_files
