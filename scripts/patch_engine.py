import os
import re
from collections import defaultdict

# Imports from your parser
from error_parser import (
    BRACE_MATCH, N64_IDENT_TYPES, N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, KNOWN_GLOBAL_TYPES, N64_AUDIO_STATE_TYPES, 
    POSIX_RESERVED_NAMES, read_file, write_file
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
    """Ensure n64_types.h exists, cleans up bad macros, and injects primitives & audio states."""
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
    else:
        content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
        os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)

    required_types = [
        ("#include <stdint.h>", "#include <stdint.h>"),
        ("typedef uint32_t u32;", "typedef uint8_t u8;\ntypedef int8_t s8;\ntypedef uint16_t u16;\ntypedef int16_t s16;\ntypedef uint32_t u32;\ntypedef int32_t s32;\ntypedef uint64_t u64;\ntypedef int64_t s64;\ntypedef float f32;\ntypedef double f64;")
    ]
    
    changed = False
    for check, injection in required_types:
        if check not in content:
            content = content.replace("#pragma once", f"#pragma once\n{injection}\n")
            changed = True
            
    # BUG FIX: Purge any bad auto-macros that were accidentally injected for Audio States
    for t in N64_AUDIO_STATE_TYPES:
        bad_macro = f"\n#ifndef {t}\n#define {t} 0 /* AUTO-INJECTED UNKNOWN MACRO */\n#endif\n"
        if bad_macro in content:
            content = content.replace(bad_macro, "")
            changed = True
            
    for t in N64_AUDIO_STATE_TYPES:
        if f"typedef struct {t}" not in content and f"}} {t};" not in content:
            content += f"\ntypedef struct {t} {{ long long int force_align[64]; }} {t};\n"
            changed = True
            
    if changed or not os.path.exists(TYPES_HEADER):
        write_file(TYPES_HEADER, content)
        
    return content

def canonical_tag(name):
    if len(name) > 1 and name[0].islower() and name[1].isupper():
        base = name[1].lower() + name[2:]
        return base + "_s"
    return name + "_s"

def remove_conflicting_fwd_decl(content, alias):
    expected_tag = canonical_tag(alias)
    pat = re.compile(
        r'/\* AUTO: forward decl[^\n]*/\n'
        r'typedef\s+struct\s+' + re.escape(expected_tag) + r'\s+' + re.escape(alias) + r'\s*;\n?'
    )
    new_content, n = pat.subn("", content)
    if n == 0:
        pat2 = re.compile(r'typedef\s+struct\s+' + re.escape(expected_tag) + r'\s+' + re.escape(alias) + r'\s*;\n?')
        new_content, n = pat2.subn("", content)
    return new_content, n > 0

def fix_body_tag(content, alias):
    expected = canonical_tag(alias)
    pat = re.compile(
        r'(typedef\s+struct\s+)(\w+)(\s*\{[^{}]*\}\s*(?:[^;]*\b)' + re.escape(alias) + r'\b[^;]*;)',
        re.DOTALL
    )
    changed = False
    def _sub(m):
        nonlocal changed
        if m.group(2) == expected: return m.group(0)
        changed = True
        return m.group(1) + expected + m.group(3)
    new_content = pat.sub(_sub, content)
    return new_content, changed

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

    if categories["extraneous_brace"]:
        original = types_content
        types_content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", types_content)
        types_content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    for filepath, func in sorted(categories["conflicting_types"]):
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

    for filepath in sorted(categories["missing_n64_types"]):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        if 'include "ultra/n64_types.h"' not in content:
            write_file(filepath, '#include "ultra/n64_types.h"\n' + content)
            fixed_files.add(filepath)
            fixes += 1

    for filepath in sorted(categories["actor_pointer"]):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        original = content
        if "Actor *actor =" not in content and "this" in content:
            content = re.sub(r'\)\s*\{', r') {\n    Actor *actor = (Actor *)this;', content, count=1)
        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories["local_struct_fwd"]:
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
    for filepath, _, _ in categories["typedef_redef"]: fixd_files.add(filepath)
    for filepath, _ in categories["struct_redef"]: fixd_files.add(filepath)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
        original = content

        content = strip_auto_preamble(content)

        tagged_body_re = re.compile(
            rf'(?:typedef\s+)?struct\s+(\w+)\s*\{{({BRACE_MATCH})\}}\s*[^;]*;',
            re.DOTALL
        )
        tag_matches = defaultdict(list)
        for m in tagged_body_re.finditer(content): tag_matches[m.group(1)].append(m)
        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]): content = content[:m.start()] + content[m.end():]

        for fp2, type1, type2 in categories["typedef_redef"]:
            if fp2 != filepath: continue
            t1_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type1)
            t2_m = re.search(r"struct ([A-Za-z_][A-Za-z0-9_]*)", type2)
            tag1 = t1_m.group(1) if t1_m else None
            tag2 = t2_m.group(1) if t2_m else None
            if not (tag1 and tag2 and tag1 != tag2): continue
            
            target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
            alias = tag1 if target_tag == tag2 else tag2

            if alias in KNOWN_GLOBAL_TYPES or target_tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    rf'(?:typedef\s+)?struct\s+{re.escape(target_tag)}?\s*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(alias)}\b[^;]*;\n?',
                    "", content
                )
                content = re.sub(rf'typedef\s+struct\s+{re.escape(target_tag)}\s+{re.escape(alias)}\s*;\n?', '', content)
                continue
            
            anon_body_pattern = rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_body_pattern, content):
                def _anon_sub(m, tt=target_tag):
                    body_inner = m.group(1)
                    declarator = m.group(2)
                    return f"typedef struct {tt} {{{body_inner}}} {declarator};"
                content, _ = re.subn(anon_body_pattern, _anon_sub, content)
            else:
                content, _ = re.subn(
                    r"\bstruct\s+" + re.escape(alias) + r"\b",
                    f"struct {target_tag}", content
                )

        for fp2, tag in categories["struct_redef"]:
            if fp2 != filepath: continue
            if tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    rf'struct\s+{re.escape(tag)}\s*\{{({BRACE_MATCH})\}}\s*;\n?',
                    "", content
                )

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories["incomplete_sizeof"]:
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

    if categories["undeclared_macros"]:
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

    if categories["implicit_func"]:
        math_funcs   = {"sinf", "cosf", "sqrtf", "abs", "fabs", "pow", "floor", "ceil", "round"}
        string_funcs = {"memcpy", "memset", "strlen", "strcpy", "strncpy", "strcmp", "memcmp"}
        stdlib_funcs = {"malloc", "free", "exit", "atoi", "rand", "srand"}
        types_content = read_file(TYPES_HEADER)
        includes_added = False
        for func in sorted(categories["implicit_func"]):
            if func in math_funcs:       header = "<math.h>"
            elif func in string_funcs:   header = "<string.h>"
            elif func in stdlib_funcs:   header = "<stdlib.h>"
            else:                        continue
            if f"#include {header}" not in types_content:
                types_content = types_content.replace("#pragma once", f"#pragma once\n#include {header}")
                includes_added = True
        if includes_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["undefined_symbols"]:
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

    for cat in ["audio_states", "missing_types"]:
        if categories.get(cat):
            types_content = read_file(TYPES_HEADER)
            types_added   = False
            
            for filepath, tag in sorted(categories[cat]):
                if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                    c = read_file(filepath)
                    if 'include "ultra/n64_types.h"' not in c:
                        write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                        fixed_files.add(filepath); fixes += 1

                if tag in N64_AUDIO_STATE_TYPES:
                    if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                        types_content += f"\ntypedef struct {tag} {{ long long int force_align[64]; }} {tag};\n"
                        types_added = True
                    continue

                base_tag = tag[:-2] if tag.endswith("_s") else tag
                if base_tag in N64_STRUCT_BODIES or tag in KNOWN_GLOBAL_TYPES:
                    if base_tag in N64_STRUCT_BODIES:
                        categories["need_struct_body"].add(base_tag)
                    continue
                        
                if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                    types_content += f"\ntypedef struct {tag} {{ int dummy_data[128]; }} {tag};\n"
                    types_added = True
                    
            if types_added:
                write_file(TYPES_HEADER, types_content); fixes += 1

    if categories["undeclared_n64_types"]:
        types_content = read_file(TYPES_HEADER)
        k_added = False
        if "OSIntMask" in categories["undeclared_n64_types"]:
            if "OSIntMask" not in types_content:
                types_content += "\n/* N64 interrupt mask type */\ntypedef u32 OSIntMask;\n"
                k_added = True
            for macro, val in sorted(KNOWN_MACROS.items()):
                if macro.startswith("OS_IM_") and f"#define {macro}" not in types_content:
                    types_content += f"\n#ifndef {macro}\n#define {macro} {val}\n#endif\n"
                    k_added = True
        if k_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1
        if os.path.exists(STUBS_FILE):
            existing_stubs = read_file(STUBS_FILE)
            if "osSetIntMask" not in existing_stubs:
                existing_stubs += "OSIntMask osSetIntMask(OSIntMask mask) { (void)mask; return 0; }\n"
                write_file(STUBS_FILE, existing_stubs)
                fixes += 1

    if categories["undeclared_gbi"]:
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

    if categories["need_mtx_body"]:
        types_content = read_file(TYPES_HEADER)
        if "i[4][4]" not in types_content and "m[4][4]" not in types_content:
            types_content = re.sub(rf"(?:typedef\s+)?struct\s+Mtx(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:Mtx\s*)?;?\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*Mtx\s*;\n?", "", types_content)
            types_content = re.sub(r"typedef\s+struct\s+Mtx(?:_s)?\s+Mtx\s*;\n?", "", types_content)
            types_content = re.sub(r"struct\s+Mtx(?:_s)?\s*;\n?", "", types_content)
            
            types_content += "\n" + N64_STRUCT_BODIES["Mtx"]
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["need_struct_body"]:
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(categories["need_struct_body"]):
            if tag == "Mtx": continue  
            body = N64_STRUCT_BODIES.get(tag)
            
            if body:
                if tag == "LookAt": check_str = "__Light_t"
                elif tag == "OSPfs": check_str = "fileSize;"
                elif tag == "OSContStatus": check_str = "errno;"
                elif tag == "OSContPad": check_str = "stick_x;"
                elif tag == "OSPiHandle": check_str = "pageSize;"
                else: check_str = body.split('\n')[2].strip() 
                
                if check_str not in types_content:
                    types_content = re.sub(rf"(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{({BRACE_MATCH})\}}\s*(?:{re.escape(tag)}\s*)?;?\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*{re.escape(tag)}\s*;\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s+{re.escape(tag)}(?:_s)?\s+{re.escape(tag)}\s*;\n?", "", types_content)
                    types_content = re.sub(rf"struct\s+{re.escape(tag)}(?:_s)?\s*;\n?", "", types_content)
                    types_content += "\n" + body
                    bodies_added = True
        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["local_fwd_only"]:
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

    if categories["missing_globals"]:
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
