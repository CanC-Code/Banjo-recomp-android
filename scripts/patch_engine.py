import os
import re
from collections import defaultdict

from error_parser import (
    BRACE_MATCH, N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, POSIX_RESERVED_NAMES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE   = "Android/app/src/main/cpp/ultra/n64_stubs.c"

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
    """Ensure n64_types.h exists, cleans up bad macros, and injects primitives dynamically."""
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

    # 1. Safely rip out the entire CORE_PRIMITIVES block
    content = re.sub(r"(?m)^#ifndef CORE_PRIMITIVES_DEFINED\b[\s\S]*?^#endif\b[ \t]*\n?", "", content)

    # 2. Aggressively wipe out ANY loose primitive typedefs with an unstoppable regex
    primitive_types = ["u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64", "n64_bool", "OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]
    for p in primitive_types:
        pattern = rf"\btypedef\s+[^;]+\b{p}\s*;"
        content = re.sub(pattern, "", content)

    # 3. Actively scrub incorrect structural stubs for primitive N64 SDK aliases (Added OSMesg)
    for p in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]:
        content = re.sub(rf"(?:typedef\s+)?struct\s+{p}(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:{p}\s*)?;?\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*{p}\s*;\n?", "", content)
        content = re.sub(rf"typedef\s+struct\s+{p}(?:_s)?\s+{p}\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{p}(?:_s)?\s*;\n?", "", content)

    # 4. Deterministically reconstruct the core primitives
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

/* N64 SDK Primitive & Pointer Aliases */
typedef u32 OSIntMask;
typedef u64 OSTime;
typedef u32 OSId;
typedef s32 OSPri;
typedef void* OSMesg;
#endif
"""
    content = content.replace("#pragma once", f"#pragma once\n{core_primitives}", 1)
            
    if content != original_content:
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
        pattern1 = rf"(?m)^\s*#ifndef {tag}\s*\n\s*#define {tag} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n\s*#endif\s*\n?"
        types_content, n1 = re.subn(pattern1, "", types_content)
        pattern2 = rf"(?m)^\s*#define {tag} 0 /\* AUTO-INJECTED UNKNOWN MACRO \*/\s*\n?"
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

    # --- DYNAMIC MISSING MEMBERS GENERATION (WITH ARRAY HEURISTICS) ---
    for struct_name, member_name in sorted(categories.get("missing_members", [])):
        types_content = read_file(TYPES_HEADER)
        pattern = rf"(struct\s+{struct_name}\s*\{{)([^}}]*?)(\}})"
        
        # SMART HEURISTIC: Inject arrays or pointers based on member names
        array_names = {"id", "label", "name", "buffer", "data", "str", "string", "temp"}
        
        def inject_member(match):
            body = match.group(2)
            if member_name not in body:
                if member_name in array_names:
                    return f"{match.group(1)}{body}    unsigned char {member_name}[128]; /* AUTO-ARRAY */\n{match.group(3)}"
                elif "ptr" in member_name.lower() or "func" in member_name.lower() or "cb" in member_name.lower() or "msg" in member_name.lower():
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
                injected_field = f"unsigned char {member_name}[128]; /* AUTO-ARRAY */"
            elif "ptr" in member_name.lower() or "func" in member_name.lower() or "cb" in member_name.lower() or "msg" in member_name.lower():
                injected_field = f"void* {member_name}; /* AUTO-POINTER */"
            else:
                injected_field = f"long long int {member_name};"
                
            types_content += f"\nstruct {struct_name} {{\n    {injected_field}\n    long long int force_align[64];\n}};\n"
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    # --- DYNAMIC VARIABLE REDEFINITION FIXES ---
    for filepath, var in sorted(categories.get("redefinition", [])):
        if os.path.exists(filepath):
            content = read_file(filepath)
            new_content, n = re.subn(rf"^(.*?\b{re.escape(var)}\b.*?;)", r"/* AUTO-REMOVED REDEF: \1 */", content, flags=re.MULTILINE)
            if n > 0:
                write_file(filepath, new_content)
                fixed_files.add(filepath)
                fixes += 1

    # --- DYNAMIC MISSING TYPE GENERATION ---
    for filepath, tag in sorted(categories.get("missing_types", [])):
        types_content = read_file(TYPES_HEADER)
        if tag in N64_STRUCT_BODIES:
            categories.setdefault("need_struct_body", set()).add(tag)
        else:
            if tag in ["OSIntMask", "OSTime", "OSId", "OSPri", "OSMesg"]: continue
            
            struct_tag = f"{tag}_s" if not tag.endswith("_s") else tag
            decl = f"struct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {tag};\n"
            
            if f"struct {struct_tag}" not in types_content and f" {tag};" not in types_content:
                types_content += f"\n#ifndef {tag}_DEFINED\n#define {tag}_DEFINED\n{decl}#endif\n"
                write_file(TYPES_HEADER, types_content)
                fixed_files.add(TYPES_HEADER)
                fixes += 1
            
        if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
            c = read_file(filepath)
            if 'include "ultra/n64_types.h"' not in c:
                write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                fixed_files.add(filepath)
                fixes += 1

    # STANDARD FIXES
    if categories.get("extraneous_brace", False):
        original = types_content
        types_content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", types_content)
        types_content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    for filepath, func in sorted(categories.get("conflicting_types", [])):
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
                if includes:
                    idx = includes[-1].end()
                    content = content[:idx] + injection + content[idx:]
                else:
                    content = injection + content
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

    for filepath in sorted(categories.get("missing_n64_types", [])):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath)
            fixes += 1

    for filepath in sorted(categories.get("actor_pointer", [])):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        original = content
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories.get("local_struct_fwd", []):
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_struct_fwd"]: file_to_types[filepath].add(type_name)
        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            fwd_lines = []
            for t in sorted(type_names):
                tag = t[1].lower() + t[2:] if len(t) > 1 and t[0] in ('s', 'S') else t
                fwd_decl = f"typedef struct {tag}_s {t};"
                if fwd_decl not in content: fwd_lines.append(fwd_decl)
            if fwd_lines:
                injection = "/* AUTO: forward declarations */\n" + "\n".join(fwd_lines) + "\n"
                write_file(filepath, injection + content)
                fixed_files.add(filepath)
                fixes += 1

    fixd_files = set()
    for filepath, _, _ in categories.get("typedef_redef", []): fixd_files.add(filepath)
    for filepath, _ in categories.get("struct_redef", []): fixd_files.add(filepath)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        original = content
        content = strip_auto_preamble(content)

        tagged_body_re = re.compile(rf'(?:typedef\s+)?struct\s+(\w+)\s*\{{({BRACE_MATCH})\}}\s*[^;]*;', re.DOTALL)
        tag_matches = defaultdict(list)
        for m in tagged_body_re.finditer(content): tag_matches[m.group(1)].append(m)
        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]): content = content[:m.start()] + content[m.end():]

        for fp2, type1, type2 in categories.get("typedef_redef", []):
            if fp2 != filepath: continue
            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2): continue
            
            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            content, cnt = re.subn(rf'(?:typedef\s+)?struct\s+{re.escape(target_tag)}?\s*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(alias)}\b[^;]*;\n?', "", content)
            content = re.sub(rf'typedef\s+struct\s+{re.escape(target_tag)}\s+{re.escape(alias)}\s*;\n?', '', content)
            
            anon_body_pattern = rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_body_pattern, content):
                def _anon_sub(m, tt=target_tag):
                    body_inner = m.group(1)
                    declarator = m.group(2)
                    return f"typedef struct {tt} {{{body_inner}}} {declarator};"
                content, _ = re.subn(anon_body_pattern, _anon_sub, content)
            else:
                content, _ = re.subn(r"\bstruct\s+" + re.escape(alias) + r"\b", f"struct {target_tag}", content)

        for fp2, tag in categories.get("struct_redef", []):
            if fp2 != filepath: continue
            content, cnt = re.subn(rf'struct\s+{re.escape(tag)}\s*\{{({BRACE_MATCH})\}}\s*;\n?', "", content)

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories.get("incomplete_sizeof", []):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen = set()
        for filepath, tag in categories["incomplete_sizeof"]:
            if tag in seen: continue
            seen.add(tag)
            base_tag = tag[:-2] if tag.endswith("_s") else tag
            if base_tag in N64_STRUCT_BODIES: continue
                
            is_sdk = (tag.isupper() or tag.startswith(("OS", "SP", "DP", "AL", "GU", "G_")) or (tag.endswith("_s") and tag[:-2].isupper()))
            if is_sdk and f"struct {tag} {{" not in types_content:
                types_content += f"\nstruct {tag} {{ long long int force_align[32]; }};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    seen_static = set()
    for cat in ["static_conflict", "posix_reserved_conflict"]:
        for filepath, func_name in categories.get(cat, []):
            key = (filepath, func_name)
            if key in seen_static: continue
            seen_static.add(key)
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            
            if func_name in POSIX_RESERVED_NAMES:
                new_content, changed = _rename_posix_static(content, func_name, filepath)
                if changed:
                    write_file(filepath, new_content)
                    fixed_files.add(filepath); fixes += 1
                continue

            prefix = os.path.basename(filepath).split('.')[0]
            macro_fix = (f"\n/* AUTO: fix static conflict */\n#define {func_name} auto_renamed_{prefix}_{func_name}\n")
            if macro_fix not in content:
                anchor = '#include "ultra/n64_types.h"'
                content = (content.replace(anchor, anchor + macro_fix) if anchor in content else macro_fix + content)
                write_file(filepath, content)
                fixed_files.add(filepath)
                fixes += 1

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
                    types_content += f"\n#ifndef {macro}\n#define {macro} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
                    macros_added = True
        if macros_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

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

    if categories.get("undefined_symbols", []):
        if not os.path.exists(STUBS_FILE):
            os.makedirs(os.path.dirname(STUBS_FILE), exist_ok=True)
            write_file(STUBS_FILE, '#include "n64_types.h"\n\n/* AUTO-GENERATED N64 SDK STUBS */\n\n')
            cmake_file = "Android/app/src/main/cpp/CMakeLists.txt"
            if os.path.exists(cmake_file):
                cmake_content = read_file(cmake_file)
                if "ultra/n64_stubs.c" not in cmake_content:
                    cmake_content = cmake_content.replace("add_library(", "add_library(\n        ultra/n64_stubs.c")
                    write_file(cmake_file, cmake_content)
        existing_stubs = read_file(STUBS_FILE)
        stubs_added = False
        for sym in sorted(categories["undefined_symbols"]):
            if sym.startswith("_Z") or "vtable" in sym: continue
            if f" {sym}(" not in existing_stubs:
                existing_stubs += f"long long int {sym}() {{ return 0; }}\n"
                stubs_added = True
        if stubs_added:
            write_file(STUBS_FILE, existing_stubs)
            fixes += 1

    if categories.get("undeclared_gbi", []):
        types_content = read_file(TYPES_HEADER)
        gbi_added = False
        for ident in sorted(categories["undeclared_gbi"]):
            if ident in KNOWN_MACROS and f"#define {ident}" not in types_content:
                types_content += f"\n#ifndef {ident}\n#define {ident} {KNOWN_MACROS[ident]}\n#endif\n"
                gbi_added = True
            elif ident not in KNOWN_MACROS:
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} 0 /* TODO: unknown GBI constant */\n#endif\n"
                    gbi_added = True
        if gbi_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("need_struct_body", []):
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(categories["need_struct_body"]):
            body = N64_STRUCT_BODIES.get(tag)
            if body:
                if not re.search(rf"\}}\s*{re.escape(tag)}\s*;", types_content) and not re.search(rf"typedef\s+struct\s+{re.escape(tag)}\b", types_content):
                    if tag == "LookAt":
                        types_content = re.sub(rf"(?m)^typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*__Light_t\s*;\n?", "", types_content)
                        types_content = re.sub(rf"(?m)^typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*__LookAtDir\s*;\n?", "", types_content)
                    if tag == "Mtx":
                        types_content = re.sub(rf"(?m)^typedef\s+union\s*\{{({BRACE_MATCH})\}}\s*__Mtx_data\s*;\n?", "", types_content)
                        
                    types_content = re.sub(rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:{re.escape(tag)}\s*)?;?\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*{re.escape(tag)}\s*;\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;\n?", "", types_content)
                    types_content = re.sub(rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
                    types_content += "\n" + body
                    bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("local_fwd_only", []):
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_fwd_only"]: file_to_types[filepath].add(type_name)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
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

    return fixes, fixed_files
