import os
import re
from collections import defaultdict

from error_parser import (
    BRACE_MATCH, N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

def deterministic_macro_val(macro_name):
    """Generates a unique but consistent integer for an unknown macro to prevent duplicate switch cases."""
    h = 0
    for c in macro_name:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    return (h % 90000) + 1000 # Returns a consistent number between 1000 and 90999

def strip_auto_preamble(content):
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
    """Ensure n64_types.h exists, cleans up bad macros, and injects primitives safely."""
    if os.path.exists(TYPES_HEADER):
        original_content = read_file(TYPES_HEADER)
        content = original_content
    else:
        original_content = ""
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    # 1. Clean up existing includes or misplaced pragmas
    content = content.replace('#include "ultra/n64_types.h"\n', '')
    
    # 2. Safely remove any existing CORE_PRIMITIVES_DEFINED blocks to prevent #if/#endif mismatches
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)

    # 3. Aggressively wipe out loose primitive typedefs that cause conflicts
    primitive_types = ["u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]
    for p in primitive_types:
        pattern = rf"(?m)^\s*typedef\s+[^;]+\b{p}\s*;\s*\n?"
        content = re.sub(pattern, "", content)

    # 4. Scrub incorrect structural stubs for primitive N64 SDK aliases
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(rf"(?:typedef\s+)?struct\s+{p}(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:{p}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*{p}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{p}(?:_s)?\s+{p}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{p}(?:_s)?\s*;\n?", "", content)

    # 5. Deterministically reconstruct the core primitives block and explicit OS macros
    core_primitives = """
#ifndef CORE_PRIMITIVES_DEFINED
#define CORE_PRIMITIVES_DEFINED
#include <stdint.h>
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

/* N64 SDK Primitive & Pointer Aliases */
typedef u32 OSIntMask;
typedef u64 OSTime;
typedef u32 OSId;
typedef s32 OSPri;
typedef void* OSMesg;

/* Common N64 OS Macros to prevent duplicate case values */
#ifndef OS_READ
#define OS_READ 0
#endif
#ifndef OS_WRITE
#define OS_WRITE 1
#endif
#ifndef OS_MESG_NOBLOCK
#define OS_MESG_NOBLOCK 0
#endif
#ifndef OS_MESG_BLOCK
#define OS_MESG_BLOCK 1
#endif

#endif
"""
    # Force #pragma once at the top and followed by core primitives
    content = content.replace("#pragma once", "").strip()
    content = "#pragma once\n" + core_primitives + "\n" + content
            
    if content.strip() != original_content.strip():
        write_file(TYPES_HEADER, content)
        
    return content

def _rename_posix_static(content, func_name, filepath):
    prefix    = os.path.basename(filepath).split('.')[0]
    new_name  = f"n64_{prefix}_{func_name}"
    define    = f"\n/* AUTO: rename POSIX-reserved static '{func_name}' */\n#define {func_name} {new_name}\n"
    if define in content:
        return content, False
    includes = list(re.finditer(r'#include\s+.*?\n', content))
    idx = includes[-1].end() if includes else 0
    return content[:idx] + define + content[idx:], True

def apply_fixes(categories):
    fixes = 0
    fixed_files = set()

    types_content = ensure_types_header_base()

    # --- DYNAMIC MACRO SCRUBBER ---
    known_types = set()
    for _, tag in categories.get("missing_types", []): known_types.add(tag)
    for tag in categories.get("need_struct_body", []): known_types.add(tag)
    for filepath, tag in categories.get("incomplete_sizeof", []): known_types.add(tag)
    for tag in categories.get("conflict_typedef", []): known_types.add(tag)
    
    macros_cleaned = False
    for tag in known_types:
        # Scrub dynamically injected macros holding digits
        pattern1 = rf"(?m)^\s*#ifndef {re.escape(tag)}\s*\n\s*#define {re.escape(tag)} \d+ /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(pattern1, "", types_content)
        pattern2 = rf"(?m)^\s*#define {re.escape(tag)} \d+ /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
        types_content, n2 = re.subn(pattern2, "", types_content)
        if n1 > 0 or n2 > 0:
            macros_cleaned = True
            fixes += 1
            
    if macros_cleaned:
        write_file(TYPES_HEADER, types_content)

    # --- DYNAMIC STRUCT REDEFINITION FIXES ---
    for type_name in sorted(categories.get("conflict_typedef", [])):
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(?:typedef\s+)?struct\s+{type_name}\s*\{{[^}}]*\}}\s*{type_name}?\s*;\n?"
        new_types, n = re.subn(pattern, "", types_content)
        if n > 0:
            if f"struct {type_name}_s {{" not in new_types:
                new_types += f"\nstruct {type_name}_s {{ long long int force_align[64]; }};\n"
            write_file(TYPES_HEADER, new_types)
            types_content = new_types
            fixes += 1

    # --- DYNAMIC MISSING MEMBERS GENERATION ---
    for struct_name, member_name in sorted(categories.get("missing_members", [])):
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"
        array_names = {"id", "label", "name", "buffer", "data", "str", "string", "temp"}
        
        def inject_member(match):
            body = match.group(2)
            if member_name not in body:
                if member_name in array_names:
                    return f"{match.group(1)}{body}    unsigned char {member_name}[128]; /* AUTO-ARRAY */\n{match.group(3)}"
                elif any(x in member_name.lower() for x in ["ptr", "func", "cb", "msg"]):
                    return f"{match.group(1)}{body}    void* {member_name}; /* AUTO-POINTER */\n{match.group(3)}"
                else:
                    return f"{match.group(1)}{body}    long long int {member_name};\n{match.group(3)}"
            return match.group(0)
            
        if re.search(pattern, types_content):
            new_types, n = re.subn(pattern, inject_member, types_content)
            if n > 0:
                write_file(TYPES_HEADER, new_types)
                types_content = new_types
                fixes += 1
        else:
            if member_name in array_names:
                fld = f"unsigned char {member_name}[128];"
            elif any(x in member_name.lower() for x in ["ptr", "func", "cb", "msg"]):
                fld = f"void* {member_name};"
            else:
                fld = f"long long int {member_name};"
            types_content += f"\nstruct {struct_name} {{\n    {fld}\n    long long int force_align[64];\n}};\n"
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- REDEFINITION & TYPE GENERATION ---
    for filepath, var in sorted(categories.get("redefinition", [])):
        if os.path.exists(filepath):
            content = read_file(filepath)
            new_content, n = re.subn(rf"^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */", content, flags=re.MULTILINE)
            if n > 0:
                write_file(filepath, new_content); fixed_files.add(filepath); fixes += 1

    for filepath, tag in sorted(categories.get("missing_types", [])):
        types_content = read_file(TYPES_HEADER)
        if tag in N64_STRUCT_BODIES:
            categories.setdefault("need_struct_body", set()).add(tag)
        elif tag not in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
            struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
            decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
            if f"struct {struct_tag}" not in types_content and f" {tag};" not in types_content:
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content); fixed_files.add(TYPES_HEADER); fixes += 1
        
        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            if 'include "ultra/n64_types.h"' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c); fixed_files.add(filepath); fixes += 1

    # --- CONFLICTING PROTOTYPES & STATIC CONFLICTS ---
    for filepath, func in sorted(categories.get("conflicting_types", [])):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        pattern = rf"(?:^|\n)([A-Za-z_][A-Za-z0-9_\s\*]+?)\s+\b{re.escape(func)}\s*\([^;{{]*\)\s*\{{"
        match = re.search(pattern, content)
        if match:
            sig = match.group(0)
            proto = sig[:sig.rfind('{')].strip() + ";"
            if proto not in content:
                includes = list(re.finditer(r"#include\s+.*?\n", content))
                inj = f"\n/* AUTO: resolve conflicting implicit type */\n{proto}\n"
                content = content[:includes[-1].end()] + inj + content[includes[-1].end():] if includes else inj + content
                write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    seen_static = set()
    for cat in ["static_conflict", "posix_reserved_conflict"]:
        for filepath, func_name in categories.get(cat, []):
            if (filepath, func_name) in seen_static or not os.path.exists(filepath): continue
            seen_static.add((filepath, func_name))
            content = read_file(filepath)
            if func_name in POSIX_RESERVED_NAMES:
                new_c, changed = _rename_posix_static(content, func_name, filepath)
                if changed: write_file(filepath, new_c); fixed_files.add(filepath); fixes += 1
            else:
                prefix = os.path.basename(filepath).split('.')[0]
                macro = f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n"
                if macro not in content:
                    anchor = '#include "ultra/n64_types.h"'
                    content = content.replace(anchor, anchor + macro) if anchor in content else macro + content
                    write_file(filepath, content); fixed_files.add(filepath); fixes += 1

    # --- STRUCT BODY INJECTION (SDK TYPES) ---
    if categories.get("need_struct_body", []):
        types_content = read_file(TYPES_HEADER)
        added = False
        for tag in sorted(categories["need_struct_body"]):
            body = N64_STRUCT_BODIES.get(tag)
            if body and not re.search(rf"\}}\s*{re.escape(tag)}\s*;", types_content):
                types_content = re.sub(rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:{re.escape(tag)}\s*)?;?\n?", "", types_content)
                types_content = re.sub(rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
                types_content += "\n" + body
                added = True
        if added: write_file(TYPES_HEADER, types_content); fixes += 1

    # --- UNDECLARED MACROS (Deterministic Value Injection) ---
    if categories.get("undeclared_macros", []):
        types_content = read_file(TYPES_HEADER)
        macros_added = False
        for macro in sorted(categories["undeclared_macros"]):
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
                    val = deterministic_macro_val(macro)
                    types_content += f"\n#ifndef {macro}\n#define {macro} {val} /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- IMPLICIT MATH / STRING HEADER INJECTION ---
    if categories.get("implicit_func", []):
        math_funcs   = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"stdlib.h": ["malloc", "free", "exit", "atoi", "rand", "srand"]}
        types_content = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs["stdlib.h"]:   header = "<stdlib.h>"
            else:                        continue
            if f"#include {header}" not in types_content:
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- MISSING GLOBALS & STUBS ---
    if categories.get("missing_globals", []):
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for filepath, glob in sorted(categories["missing_globals"]):
            if glob == "actor": continue
            if f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content:
                decl = f"extern void* {glob};" if glob.endswith(("_ptr", "_p")) else f"extern long long int {glob};"
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("undefined_symbols", []):
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
        existing_stubs = read_file(STUBS_FILE)
        added = False
        for sym in sorted(categories["undefined_symbols"]):
            if not sym.startswith("_Z") and "vtable" not in sym and f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                added = True
        if added: write_file(STUBS_FILE, existing_stubs); fixes += 1

    return fixes, fixed_files
