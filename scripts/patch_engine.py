import os
import re
from collections import defaultdict

# Mocking the error_parser module for demonstration
BRACE_MATCH = r"[^{}]*"
N64_STRUCT_BODIES = {
    "Mtx": "typedef struct Mtx_s {\n    float m[4][4];\n} Mtx;"
}
KNOWN_MACROS = {
    "OS_IM_1": "0x0001",
    "OS_IM_2": "0x0002",
}
KNOWN_FUNCTION_MACROS = {
    "some_macro": "#define some_macro(x) ((x) * 2)"
}
KNOWN_GLOBAL_TYPES = {"Actor", "Mtx"}

def read_file(filepath):
    with open(filepath, 'r') as file:
        return file.read()

def write_file(filepath, content):
    with open(filepath, 'w') as file:
        file.write(content)

TYPES_HEADER = "Android/app/src/main/cpp/ultra/n64_types.h"
STUBS_FILE = "Android/app/src/main/cpp/ultra/n64_stubs.c"

def strip_auto_preamble(content):
    """Removes automatically injected forward declarations to prevent duplicates."""
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
    """Ensures the base types header file exists and has a pragma once guard."""
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
    """Iterates through parsed compilation errors and applies automatic code fixes."""
    fixes = 0
    fixed_files = set()

    types_content = ensure_types_header_base()

    if categories.get("extraneous_brace"):
        original = types_content
        types_content = re.sub(r"struct\s+[A-Za-z_]\w*\s*\{\s*long\s+long\s+int\s+force_align\[32\];\s*\};\n", "", types_content)
        types_content = re.sub(r"typedef\s+struct\s+([A-Za-z_]\w*)\s+\w+\s*\{", r"typedef struct \1 {", types_content)
        if types_content != original:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    for filepath, func in sorted(categories.get("conflicting_types", [])):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        pattern = r"(?:^|\n)([A-Za-z_][^;{]*?\b{}\b\s*\([^;{{]*\))\s*{{".format(re.escape(func))
        match = re.search(pattern, content)
        if match:
            prototype = match.group(1).strip() + ";"
            prototype = re.sub(r'//.*', '', prototype)
            prototype = re.sub(r'/\*.*?\*/', '', prototype, flags=re.DOTALL)
            prototype = re.sub(r'\s+', ' ', prototype).strip()

            normalized_content = re.sub(r'\s+', ' ', content)
            if prototype not in normalized_content:
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

    if categories.get("local_struct_fwd"):
        file_to_types = defaultdict(set)
        for filepath, type_name in categories["local_struct_fwd"]:
            file_to_types[filepath].add(type_name)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
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

    fixd_files = set()
    for filepath, _, _ in categories.get("typedef_redef", []): fixd_files.add(filepath)
    for filepath, _ in categories.get("struct_redef", []): fixd_files.add(filepath)

    for filepath in sorted(fixd_files):
        if not os.path.exists(filepath): continue
        content = read_file(filepath)
        original = content

        content = strip_auto_preamble(content)

        tagged_body_re = re.compile(
            r'(?:typedef\s+)?struct\s+(\w+)\s*\{([^{}]*)\}\s*[^;]*;',
            re.DOTALL
        )
        tag_matches = defaultdict(list)
        for m in tagged_body_re.finditer(content):
            tag_matches[m.group(1)].append(m)

        for tag, matches in tag_matches.items():
            if len(matches) > 1:
                for m in reversed(matches[:-1]):
                    content = content[:m.start()] + content[m.end():]

        for fp2, type1, type2 in categories.get("typedef_redef", []):
            if fp2 != filepath: continue

            t1 = type1.replace("struct ", "").strip()
            t2 = type2.replace("struct ", "").strip()
            if t1.startswith("("): t1 = ""
            if t2.startswith("("): t2 = ""

            target_tag = t2 if t2.endswith("_s") else (t1 if t1.endswith("_s") else t2)
            alias = t1 if target_tag == t2 else t2

            if alias in KNOWN_GLOBAL_TYPES or target_tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    r'(?:typedef\s+)?struct\s+(?:{}|{})?\s*\{[^{}]*\}[^;]*\b{}\b[^;]*;\n?'.format(re.escape(target_tag), re.escape(alias), re.escape(alias)),
                    "", content
                )
                content = re.sub(r'typedef\s+struct\s+(?:{}|{})\s+[^;]*\b{}\b[^;]*;\n?'.format(re.escape(target_tag), re.escape(alias), re.escape(alias)), '', content)
                continue

            anon_body_pattern = r"typedef\s+struct\s*\{[^{}]*\}\s*([^;]*\b{}\b[^;]*);".format(re.escape(alias))
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

        for fp2, tag in categories.get("struct_redef", []):
            if fp2 != filepath: continue
            if tag in KNOWN_GLOBAL_TYPES:
                content, cnt = re.subn(
                    r'struct\s+{}\s*\{[^{}]*\};'.format(re.escape(tag)),
                    "", content
                )

        if content != original:
            write_file(filepath, content)
            fixed_files.add(filepath)
            fixes += 1

    if categories.get("incomplete_sizeof"):
        types_content = read_file(TYPES_HEADER)
        types_added = False
        seen = set()
        for filepath, tag in categories["incomplete_sizeof"]:
            if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                c = read_file(filepath)
                if 'include "ultra/n64_types.h"' not in c:
                    write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                    fixed_files.add(filepath)
                    fixes += 1

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
    for filepath, func_name in categories.get("static_conflict", []):
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

    if categories.get("undeclared_macros"):
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

    if categories.get("implicit_func"):
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

    if categories.get("undefined_symbols"):
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

    if categories.get("audio_states"):
        types_content = read_file(TYPES_HEADER)
        audio_added = False
        for t in sorted(categories["audio_states"]):
            if f"typedef struct {t}" not in types_content:
                types_content += f"\ntypedef struct {t} {{ long long int force_align[32]; }} {t};\n"
                audio_added = True
        if audio_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("undeclared_n64_types"):
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

    if categories.get("undeclared_gbi"):
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

    if categories.get("missing_types"):
        types_content = read_file(TYPES_HEADER)
        types_added = False

        mt = categories["missing_types"]
        if not isinstance(mt, (list, set, tuple)): mt = []

        for item in sorted(mt, key=str):
            filepath = None
            if isinstance(item, tuple) and len(item) >= 2:
                filepath, tag = item[0], item[1]
            else:
                tag = item

            base_tag = tag[:-2] if tag.endswith("_s") else tag

            if base_tag in N64_STRUCT_BODIES or tag in KNOWN_GLOBAL_TYPES:
                if filepath and os.path.exists(filepath) and not filepath.endswith("n64_types.h"):
                    c = read_file(filepath)
                    if 'include "ultra/n64_types.h"' not in c:
                        write_file(filepath, '#include "ultra/n64_types.h"\n' + c)
                        fixed_files.add(filepath)
                        fixes += 1

                if base_tag in N64_STRUCT_BODIES:
                    if isinstance(categories.get("need_struct_body"), set):
                        categories["need_struct_body"].add(base_tag)
                    elif isinstance(categories.get("need_struct_body"), list):
                        categories["need_struct_body"].append(base_tag)
                    else:
                        categories["need_struct_body"] = {base_tag}
                    continue

            if f"typedef struct {tag}" not in types_content and f"}} {tag};" not in types_content:
                types_content += f"\ntypedef struct {tag} {{ int dummy_data[128]; }} {tag};\n"
                types_added = True

        if types_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("need_struct_body"):
        types_content = read_file(TYPES_HEADER)
        bodies_added = False

        nsb = categories["need_struct_body"]
        if not isinstance(nsb, (list, set, tuple)): nsb = []

        for raw_tag in sorted(nsb):
            tag = raw_tag[:-2] if raw_tag.endswith("_s") else raw_tag
            if tag == "Mtx":
                categories["need_mtx_body"] = True
                continue
            body = N64_STRUCT_BODIES.get(tag)

            check_str = f"typedef struct {tag}_s {{"
            if tag == "LookAt": check_str = "__LookAtDir l[2];"
            elif tag == "OSPfs": check_str = "u8 activebank;"
            elif tag == "OSContStatus": check_str = "u16 type;"
            elif tag == "OSContPad": check_str = "s8  stick_x;"
            elif tag == "OSPiHandle": check_str = "u8 pageSize;"

            needs_injection = False
            if body:
                if check_str not in types_content:
                    needs_injection = True
                elif not body.startswith("typedef union") and f"struct {tag}_s {{" not in types_content:
                    needs_injection = True

            if needs_injection:
                types_content = re.sub(rf"(?:typedef\s+)?struct\s*(?:{re.escape(tag)}|{re.escape(tag)}_s)?\s*\{{[^{}]*}}\s*[^;]*\b(?:{re.escape(tag)}|{re.escape(tag)}_s)\b[^;]*;\n?", "", types_content)
                types_content = re.sub(rf"struct\s+(?:{re.escape(tag)}|{re.escape(tag)}_s)\s*\{{[^{}]*}}\s*;\n?", "", types_content)
                types_content = re.sub(rf"typedef\s+(?:struct\s+)?(?:{re.escape(tag)}|{re.escape(tag)}_s)\s+[^;]*\b(?:{re.escape(tag)}|{re.escape(tag)}_s)\b[^;]*;\n?", "", types_content)
                types_content = re.sub(rf"struct\s+(?:{re.escape(tag)}|{re.escape(tag)}_s)\s*;\n?", "", types_content)

                if tag == "LookAt":
                    types_content = re.sub(rf"typedef\s+struct\s*\{{[^{}]*}}\s*__Light_t\s*;\n?", "", types_content)
                    types_content = re.sub(rf"typedef\s+struct\s*\{{[^{}]*}}\s*__LookAtDir\s*;\n?", "", types_content)

                if not body.startswith("typedef union") and f"struct {tag}_s" not in body:
                    body = re.sub(rf"typedef\s+struct\s*(?:{re.escape(tag)})?\s*\{{", f"typedef struct {tag}_s {{", body, count=1)

                types_content += "\n" + body
                bodies_added = True

        if bodies_added:
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("need_mtx_body"):
        types_content = read_file(TYPES_HEADER)
        if "i[4][4]" not in types_content and "m[4][4]" not in types_content:
            types_content = re.sub(rf"(?:typedef\s+)?struct\s*(?:Mtx|Mtx_s)?\s*\{{[^{}]*}}\s*[^;]*\b(?:Mtx|Mtx_s)\b[^;]*;\n?", "", types_content)
            types_content = re.sub(rf"struct\s+(?:Mtx|Mtx_s)\s*\{{[^{}]*}}\s*;\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+(?:struct\s+)?(?:Mtx|Mtx_s)\s+[^;]*\b(?:Mtx|Mtx_s)\b[^;]*;\n?", "", types_content)
            types_content = re.sub(rf"struct\s+(?:Mtx|Mtx_s)\s*;\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+union\s*\{{[^{}]*}}\s*__Mtx_data\s*;\n?", "", types_content)
            types_content = re.sub(rf"typedef\s+union\s*(?:Mtx|Mtx_s)?\s*\{{[^{}]*}}\s*[^;]*\b(?:Mtx|Mtx_s)\b[^;]*;\n?", "", types_content)

            types_content += "\n" + N64_STRUCT_BODIES["Mtx"]
            write_file(TYPES_HEADER, types_content)
            fixes += 1

    if categories.get("local_fwd_only"):
        file_to_types = defaultdict(set)
        for filepath, type_name in categories.get("local_fwd_only", []):
            file_to_types[filepath].add(type_name)

        for filepath, type_names in sorted(file_to_types.items()):
            if not os.path.exists(filepath) or filepath.endswith("n64_types.h"): continue
            content = read_file(filepath)
            content = strip_auto_preamble(content)
            changed = False
            for t in sorted(type_names):
                body_pattern = rf"typedef\s+struct[^{{]*\{{[^{}]*}}\s*[^;]*\b{re.escape(t)}\b[^;]*;"
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

    if categories.get("missing_globals"):
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

    return fixes, fixed_files