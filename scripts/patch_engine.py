import os
import re
from collections import defaultdict
from error_parser import (
    BRACE_MATCH, N64_STRUCT_BODIES, KNOWN_MACROS, 
    KNOWN_FUNCTION_MACROS, KNOWN_GLOBAL_TYPES, read_file, write_file
)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE = "Android/app/src/main/cpp/ultra/n64_stubs.c"

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
    if os.path.exists(TYPES_HEADER):
        content = read_file(TYPES_HEADER)
        if "#pragma once" not in content:
            content = "#pragma once\n" + content
            write_file(TYPES_HEADER, content)
        return content
    content = "#pragma once\n\n/* AUTO-GENERATED N64 compatibility types */\n\n"
    os.makedirs(os.path.dirname(TYPES_HEADER), exist_ok=True)
    write_file(TYPES_HEADER, content)
    return content

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

    # Inject missing matrix and core SDK prototypes directly into n64_types.h
    sdk_prototypes = [
        "void guMtxIdentF(float mf[4][4]);",
        "void guMtxIdent(Mtx *m);",
        "void guMtxF2L(float mf[4][4], Mtx *m);",
        "void guMtxL2F(float mf[4][4], Mtx *m);",
        "void guTranslateF(float mf[4][4], float x, float y, float z);",
        "void guScaleF(float mf[4][4], float x, float y, float z);",
        "void guRotateF(float mf[4][4], float a, float x, float y, float z);",
        "void guLookAtReflectF(float mf[4][4], LookAt *l, float xEye, float yEye, float zEye, float xAt, float yAt, float zAt, float xUp, float yUp, float zUp);",
        "void osCreateMesgQueue(OSMesgQueue *mq, OSMesg *msgBuf, int count);",
        "void osSetEventMesg(OSEvent e, OSMesgQueue *mq, OSMesg msg);",
        "void osCreateThread(OSThread *t, OSId id, void (*entry)(void *), void *arg, void *sp, OSPri pri);"
    ]
    for proto in sdk_prototypes:
        if proto not in types_content:
            types_content += f"\n{proto}\n"
            fixes += 1

    for filepath, func in sorted(categories["conflicting_types"]):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        pattern = rf"(?:^|\n)([A-Za-z_][A-Za-z0-9_\s\*\[\]]+?)\s+\b{re.escape(func)}\s*\([^;{{]*\)\s*\{{"
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

    # ── FIX D: Typedef / Struct Redefinition ────────────────────────────
    fixd_files = set()
    for filepath, _, _ in categories["typedef_redef"]: fixd_files.add(filepath)
    for filepath, _ in categories["struct_redef"]: fixd_files.add(filepath)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath): continue
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
            
            t1 = type1.replace("struct ", "").strip()
            t2 = type2.replace("struct ", "").strip()
            if t1.startswith("("): t1 = ""
            if t2.startswith("("): t2 = ""
            
            tag1 = t1 if t1 else None
            tag2 = t2 if t2 else None
            
            if tag1 and not tag2:
                target_tag = tag1
                alias = tag1[:-2] if tag1.endswith("_s") else tag1
            elif tag2 and not tag1:
                target_tag = tag2
                alias = tag2[:-2] if tag2.endswith("_s") else tag2
            elif tag1 and tag2:
                target_tag = tag2 if tag2.endswith("_s") else (tag1 if tag1.endswith("_s") else tag2)
                alias = tag1 if target_tag == tag2 else tag2
            else:
                continue

            if alias in KNOWN_GLOBAL_TYPES or target_tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    rf'(?:typedef\s+)?struct\s+(?:{re.escape(target_tag)}|{re.escape(alias)})?\s*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(alias)}\b[^;]*;\n?',
                    "", content
                )
                content = re.sub(rf'typedef\s+struct\s+(?:{re.escape(target_tag)}|{re.escape(alias)})\s+[^;]*\b{re.escape(alias)}\b[^;]*;\n?', '', content)
                continue
            
            anon_body_pattern = rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*([^;]*\b{re.escape(alias)}\b[^;]*);"
            if re.search(anon_body_pattern, content):
                content, cnt = re.subn(
                    anon_body_pattern,
                    lambda m: f"typedef struct {target_tag} {{{m.group(1)}}} {m.group(2)};",
                    content
                )
            else:
                content, cnt = re.subn(
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
    for filepath, func_name in categories["static_conflict"]:
        key = (filepath, func_name)
        if key in seen_static: continue
        seen_static.add(key)
        if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
        content = read_file(filepath)
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

    if categories["audio_states"]:
        types_content = read_file(TYPES_HEADER)
        audio_added = False
        for t in sorted(categories["audio_states"]):
            if f"typedef struct {t}" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

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
            types_content = re.sub(rf"(?:typedef\s+)?struct\s+(?:Mtx|Mtx_s)?\s*\{{({BRACE_MATCH})\}}\s*[^;]*\bMtx\b[^;]*;\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+struct\s+(?:Mtx|Mtx_s)\s+[^;]*\bMtx\b[^;]*;\n?", "", types_content)
            types_content = re.sub(r"struct\s+(?:Mtx|Mtx_s)\s*;\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+union\s*\{{({BRACE_MATCH})\}}\s*__Mtx_data\s*;\n?", "", types_content)
            
            types_content += "\n" + N64_STRUCT_BODIES["Mtx"]
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["need_struct_body"]:
        types_content = read_file(TYPES_HEADER)
        bodies_added = False
        for tag in sorted(categories["need_struct_body"]):
            if tag == "Mtx": continue  
            body = N64_STRUCT_BODIES.get(tag)
            
            check_str = f"typedef struct {tag}_s {{"
            if tag == "LookAt": check_str = "__LookAtDir l[2];"
            elif tag == "OSPfs": check_str = "u8 activebank;"
            elif tag == "OSContStatus": check_str = "u16 type;"
            elif tag == "OSContPad": check_str = "s8  stick_x;"
            elif tag == "OSPiHandle": check_str = "u8 pageSize;"
            
            if body and check_str not in types_content:
                types_content = re.sub(rf"(?:typedef\s+)?struct\s+(?:{re.escape(tag)}|{re.escape(tag)}_s)?\s*\{{({BRACE_MATCH})\}}\s*[^;]*\b{re.escape(tag)}\b[^;]*;\n?", "", types_content)
                types_content = re.sub(rf"typedef\s+struct\s+(?:{re.escape(tag)}|{re.escape(tag)}_s)\s+[^;]*\b{re.escape(tag)}\b[^;]*;\n?", "", types_content)
                types_content = re.sub(rf"struct\s+(?:{re.escape(tag)}|{re.escape(tag)}_s)\s*;\n?", "", types_content)
                
                if tag == "LookAt":
                    types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*__Light_t\s*;\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s*\{{({BRACE_MATCH})\}}\s*__LookAtDir\s*;\n?", "", types_content)

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

    if categories["missing_types"]:
        types_content = read_file(TYPES_HEADER)
        types_added = False
        for tag in sorted(categories["missing_types"]):
            if tag in N64_STRUCT_BODIES or tag in KNOWN_GLOBAL_TYPES: continue
            if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                types_content += f"\ntypedef struct {tag} {{ int dummy_data[128]; }} {tag};\n"
                types_added = True
        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories["missing_globals"]:
        types_content = read_file(TYPES_HEADER)
        globals_added = False
        for glob in sorted(categories["missing_globals"]):
            if glob == "actor": continue
            if f" {glob};" not in types_content and f"*{glob};" not in types_content and f" {glob}[" not in types_content:
                decl = f"extern void* {glob};" if glob.endswith(("_ptr", "_p")) else f"extern long long int {glob};"
                types_content += f"\n#ifndef {glob}_DEFINED\n#define {glob}_DEFINED\n{decl}\n#endif\n"
                globals_added = True
        if globals_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    write_file(TYPES_HEADER, types_content)
    return fixes, fixed_files
