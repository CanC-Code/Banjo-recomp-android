import os
import re
import logging
from collections import defaultdict
from typing import Dict, Set, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("N64_RECOMP_ENGINE")

class SourceConverter:
    def __init__(self, logic_dir="scripts/conversion_logic"):
        self.logic_dir = logic_dir
        self.types_header = "Android/app/src/main/cpp/ultra/n64_types.h"
        self.stubs_file = "Android/app/src/main/cpp/ultra/n64_stubs.c"
        self.dynamic_categories = defaultdict(set)
        
        # Dynamic Data Storage (Populated by Logic Files)
        self.custom_replacements = [] 
        self.MACROS = {}
        self.OPAQUE_TYPES = set()
        
        # Core Protected Primitives
        self.N64_PRIMITIVES = {
            "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
            "s8": "int8_t", "s16": "int16_t", "s32": "int32_t", "s64": "int64_t",
            "f32": "float", "f64": "double", "b32": "int32_t", "n64_bool": "int",
            "OSIntMask": "uint32_t", "OSTime": "uint64_t", "OSId": "uint32_t",
            "OSPri": "int32_t", "OSMesg": "void*"
        }

        # Base Globals (Expandable via globals.txt)
        self.N64_KNOWN_GLOBALS = {
            "__osPiTable": "struct OSPiHandle_s *__osPiTable;",
            "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
            "__osRunQueue": "struct OSThread_s *__osRunQueue;",
            "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
        }

        # Base Structs (Expandable via types.txt)
        self.N64_OS_STRUCT_BODIES = {
            "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { int16_t mi[4][4]; int16_t pad; } i; } Mtx;",
            "Vtx": "typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t; typedef union { Vtx_t v; long long int force_align[8]; } Vtx;",
            "Gfx": "typedef struct { uint32_t words[2]; } Gfx;",
            "Acmd": "typedef long long int Acmd;",
            "OSThread": "typedef union __OSThreadContext_u { struct { uint64_t pc; uint64_t a0; uint64_t sp; uint64_t ra; uint32_t sr; uint32_t rcp; uint32_t fpcsr; } regs; long long int force_align[67]; } __OSThreadContext;\ntypedef struct OSThread_s { struct OSThread_s *next; int32_t priority; struct OSThread_s **queue; struct OSThread_s *tlnext; uint16_t state; uint16_t flags; uint64_t id; int fp; __OSThreadContext context; } OSThread;"
        }

    def load_logic(self):
        """Loads all static rules from the logic directory."""
        if not os.path.exists(self.logic_dir):
            os.makedirs(self.logic_dir, exist_ok=True)
            logger.info(f"📂 Created empty logic directory at {self.logic_dir}")
            return True
        
        logger.info(f"📂 Loading logic files from {self.logic_dir}...")
        for filename in os.listdir(self.logic_dir):
            path = os.path.join(self.logic_dir, filename)
            content = self.read_file(path)
            lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("#")]
            
            if "types" in filename:
                for line in lines:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        self.N64_OS_STRUCT_BODIES[k.strip()] = v.strip()
            
            elif "macros" in filename:
                for line in lines:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        self.MACROS[k.strip()] = v.strip()

            elif "opaque" in filename:
                for line in lines:
                    self.OPAQUE_TYPES.add(line.strip())

            elif "globals" in filename:
                for line in lines:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        self.N64_KNOWN_GLOBALS[k.strip()] = v.strip()
            
            elif "replacements" in filename:
                for line in lines:
                    if "->" in line:
                        pat, rep = line.split("->", 1)
                        self.custom_replacements.append((pat.strip(), rep.strip()))
            
            elif "stubs" in filename:
                for line in lines:
                    self.dynamic_categories["implicit_functions"].add(line.strip())

        return True

    def read_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception: return ""

    def write_file(self, file_path: str, content: str):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def scrape_logs(self, log_content: str):
        """Dynamically learns from compiler errors."""
        self.dynamic_categories = defaultdict(set)
        for m in re.finditer(r"unknown type name ['\"](.*?)['\"]", log_content):
            tag = m.group(1).strip()
            if tag not in self.N64_PRIMITIVES:
                self.dynamic_categories["missing_types"].add(tag)
        for m in re.finditer(r"incomplete (?:element )?type ['\"](?:struct )?(.*?)['\"]", log_content):
            self.dynamic_categories["need_body"].add(m.group(1).strip())
        for m in re.finditer(r"use of undeclared identifier ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["undeclared_identifiers"].add(m.group(1).strip())
        for m in re.finditer(r"implicit declaration of function ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["implicit_functions"].add(m.group(1).strip())

    def apply_dynamic_fixes(self):
        """Applies learned/logic rules to stubs and types."""
        if not os.path.exists(self.types_header): return
        content = self.read_file(self.types_header)
        stubs = self.read_file(self.stubs_file) if os.path.exists(self.stubs_file) else '#include "ultra/n64_types.h"\n'
        
        updated_types = False
        updated_stubs = False

        # Missing opaque types / missing types
        for typ in self.dynamic_categories.get("missing_types", set()) | self.OPAQUE_TYPES:
            if typ not in self.N64_PRIMITIVES and typ not in self.N64_OS_STRUCT_BODIES:
                if not re.search(rf"\b{typ}\b", content):
                    struct_tag = f"{typ}_s" if not typ.endswith("_s") else typ
                    content += f"\n#ifndef {typ}_DEFINED\n#define {typ}_DEFINED\nstruct {struct_tag} {{ long long int force_align[64]; }};\ntypedef struct {struct_tag} {typ};\n#endif\n"
                    updated_types = True

        # Implicit function stubs
        for func in self.dynamic_categories.get("implicit_functions", set()):
            if f"{func}_DEFINED" not in content:
                content += f"\n#ifndef {func}_DEFINED\n#define {func}_DEFINED\nextern int {func}();\n#endif"
                updated_types = True
            if f"int {func}()" not in stubs:
                stubs += f"\nint {func}() {{ return 0; }}"
                updated_stubs = True

        # Handle globals vs macros
        for ident in self.dynamic_categories.get("undeclared_identifiers", set()):
            if ident in self.MACROS:
                if f"#define {ident}" not in content:
                    content += f"\n#ifndef {ident}\n#define {ident} {self.MACROS[ident]}\n#endif\n"
                    updated_types = True
            elif ident in self.N64_KNOWN_GLOBALS:
                if f"{ident}_DEFINED" not in content:
                    content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\n#ifdef __cplusplus\nextern \"C\" {{\n#endif\nextern {self.N64_KNOWN_GLOBALS[ident]}\n#ifdef __cplusplus\n}}\n#endif\n#endif"
                    updated_types = True

        if updated_types: self.write_file(self.types_header, content)
        if updated_stubs: self.write_file(self.stubs_file, stubs)

    def strip_redefinition(self, content: str, tag: str) -> str:
        """Removes existing definitions to prevent redefinition errors."""
        content = re.sub(rf"typedef\s+[^;]*?\b{re.escape(tag)}\b\s*;\n?", "", content)
        content = re.sub(rf"struct\s+{re.escape(tag)}_s;\n?", "", content)
        pattern = re.compile(rf"\b(?:typedef\s+)?struct\s+{re.escape(tag)}(?:_s)?\s*\{{")
        match = pattern.search(content)
        if match:
            start_idx = match.start()
            brace_idx = content.find('{', start_idx)
            open_braces, curr_idx = 1, brace_idx + 1
            while curr_idx < len(content) and open_braces > 0:
                if content[curr_idx] == '{': open_braces += 1
                elif content[curr_idx] == '}': open_braces -= 1
                curr_idx += 1
            semi_idx = content.find(';', curr_idx)
            if semi_idx != -1:
                return content[:start_idx] + f"/* STRIPPED: {tag} */" + content[semi_idx+1:]
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path): return 0
        content = self.read_file(file_path)
        original = content

        if "n64_types.h" in file_path:
            content = re.sub(r'#include\s*[<"][^>"]+h[>"]\n?', '', content)
            content = re.sub(r'#pragma once\n?', '', content)
            bootstrap = "#pragma once\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\n#include <stdarg.h>\n\n"
            
            injection = "/* --- CORE DEFINITIONS --- */\n"
            for short, full in self.N64_PRIMITIVES.items():
                content = re.sub(rf"typedef\s+[^;]+?\b{short}\b\s*;\n?", "", content)
                injection += f"typedef {full} {short};\n"
            
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                content = self.strip_redefinition(content, tag)
                injection += f"{body}\n"

            content = bootstrap + injection + "\n" + content.lstrip()

        if file_path.endswith(('.c', '.cpp')):
            content = re.sub(r'(?<!extern\s)\b(?:u32|uint32_t)\s+osAppNMIBuffer\b[^;]*;', r'/* REDEF-FIX: osAppNMIBuffer definition stripped */', content)

            for pat, rep in self.custom_replacements:
                content = re.sub(pat, rep, content)

            if "this" in content and "Actor *actor =" not in content and "actor->" in content:
                content = re.sub(r'(\w+::\w+\(.*\)\s*(?:const\s+)?\{)', r'\1\n    Actor *actor = (Actor *)this;', content)

            content = re.sub(r'->context\.([a-z0-9_]+)', r'->context.regs.\1', content)
            content = re.sub(r'reinterpret_cast<\s*uint32_t\s*\*\s*>\(\s*__osRunningThread->context\s*\)', 'reinterpret_cast<uint32_t*>(&__osRunningThread->context)', content)

        if content != original:
            self.write_file(file_path, content)
            return 1
        return 0
