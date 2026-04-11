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

        # ---------------------------------------------------------------------------
        # Core Maps & POSIX Protection
        # ---------------------------------------------------------------------------
        self.N64_PRIMITIVES = {
            "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
            "s8": "int8_t", "s16": "int16_t", "s32": "int32_t", "s64": "int64_t",
            "f32": "float", "f64": "double", "b32": "int32_t"
        }

        self.POSIX_RESERVED_NAMES = {
            "close", "open", "read", "write", "send", "recv", "stat", 
            "rename", "mkdir", "rmdir", "unlink", "chmod", "chown"
        }

        self.N64_KNOWN_GLOBALS = {
            "__osPiTable": "struct OSPiHandle_s *__osPiTable;",
            "__osCurrentThread": "struct OSThread_s *__osCurrentThread;",
            "__osRunQueue": "struct OSThread_s *__osRunQueue;",
            "__osFaultedThread": "struct OSThread_s *__osFaultedThread;",
            "osTvType": "uint32_t osTvType;",
            "osRomBase": "uint32_t osRomBase;"
        }

        self.N64_OS_STRUCT_BODIES = {
            "Mtx": "typedef union { struct { float mf[4][4]; } f; struct { int16_t mi[4][4]; int16_t pad; } i; } Mtx;",
            "Vtx": "typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t; typedef union { Vtx_t v; long long int force_align[8]; } Vtx;",
            "Gfx": "typedef struct { uint32_t words[2]; } Gfx;",
            "OSMesg": "typedef void *OSMesg;",
            "OSTime": "typedef uint64_t OSTime;",
            "OSThread": """
typedef union __OSThreadContext_u {
    struct { uint64_t pc; uint64_t a0; uint64_t sp; uint64_t ra; uint32_t sr; uint32_t rcp; uint32_t fpcsr; } regs;
    long long int force_align[67];
} __OSThreadContext;
typedef struct OSThread_s {
    struct OSThread_s *next; int32_t priority; struct OSThread_s **queue; struct OSThread_s *tlnext;
    uint16_t state; uint16_t flags; uint64_t id; int fp; __OSThreadContext context;
} OSThread;""",
            "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; int32_t validCount; int32_t first; int32_t msgCount; OSMesg *msg; } OSMesgQueue;",
            "OSPiHandle": """
typedef struct { uint32_t errStatus; void *dramAddr; void *C2Addr; uint32_t sectorSize; uint32_t C1ErrNum; uint32_t C1ErrSector[4]; } __OSBlockInfo;
typedef struct { uint32_t cmdType; uint16_t transferMode; uint16_t blockNum; int32_t sectorNum; uint32_t devAddr; uint32_t bmCtlShadow; uint32_t seqCtlShadow; __OSBlockInfo block[2]; } __OSTranxInfo;
typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; __OSTranxInfo transferInfo; } OSPiHandle;"""
        }

    def load_logic(self):
        logger.info("🛠️ Loading logic (dynamic self-healing enabled)")
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
        """Deep analysis of build logs to categorize errors."""
        self.dynamic_categories = defaultdict(set)
        
        # 1. Unknown types
        for m in re.finditer(r"unknown type name ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["missing_types"].add(m.group(1).strip())
            
        # 2. Undeclared identifiers (macros/globals)
        for m in re.finditer(r"use of undeclared identifier ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["undeclared_identifiers"].add(m.group(1).strip())
            
        # 3. Implicit function declarations
        for m in re.finditer(r"implicit declaration of function ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["implicit_functions"].add(m.group(1).strip())

        # 4. POSIX static conflicts
        for m in re.finditer(r"static declaration of ['\"](.*?)['\"] follows non-static", log_content):
            self.dynamic_categories["posix_conflict"].add(m.group(1).strip())

        logger.info(f"📊 Scraped {sum(len(v) for v in self.dynamic_categories.values())} issues from log.")

    def apply_dynamic_fixes(self):
        """Apply scraped fixes to n64_types.h and n64_stubs.c."""
        if not os.path.exists(self.types_header): return
        
        types_content = self.read_file(self.types_header)
        stubs_content = self.read_file(self.stubs_file) if os.path.exists(self.stubs_file) else '#include "n64_types.h"\n'
        
        updated_types = False
        updated_stubs = False

        # Fix missing types
        for typ in self.dynamic_categories.get("missing_types", set()):
            if not re.search(rf"\b{typ}\b", types_content):
                if typ in self.N64_PRIMITIVES:
                    types_content += f"\ntypedef {self.N64_PRIMITIVES[typ]} {typ};"
                else:
                    types_content += f"\ntypedef struct {typ}_s {typ};"
                updated_types = True

        # Fix implicit functions (Prototypes in header, stubs in .c)
        for func in self.dynamic_categories.get("implicit_functions", set()):
            if f"{func}_DEFINED" not in types_content:
                types_content += f"\n#ifndef {func}_DEFINED\n#define {func}_DEFINED\nextern int {func}();\n#endif"
                updated_types = True
            if f"int {func}()" not in stubs_content:
                stubs_content += f"\nint {func}() {{ return 0; }}"
                updated_stubs = True

        # Fix undeclared identifiers (check for known globals first)
        for ident in self.dynamic_categories.get("undeclared_identifiers", set()):
            if ident in self.N64_KNOWN_GLOBALS:
                if f"{ident}_DEFINED" not in types_content:
                    types_content += f"\n#ifndef {ident}_DEFINED\n#define {ident}_DEFINED\nextern {self.N64_KNOWN_GLOBALS[ident]}\n#endif"
                    updated_types = True
            elif ident.isupper(): # Likely a macro
                if f"#define {ident}" not in types_content:
                    types_content += f"\n#ifndef {ident}\n#define {ident} 0\n#endif"
                    updated_types = True

        if updated_types: self.write_file(self.types_header, types_content)
        if updated_stubs: self.write_file(self.stubs_file, stubs_content)

    def strip_redefinition(self, content: str, tag: str) -> str:
        """Brace-matched removal of any struct/typedef definition for tag."""
        pattern = re.compile(rf"\b(?:typedef\s+)?struct\s+{re.escape(tag)}\s*\{{")
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
            # Bootstrap standard types
            if "#include <stdint.h>" not in content:
                content = content.replace("#pragma once", "#pragma once\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>")
            
            for short, full in self.N64_PRIMITIVES.items():
                if not re.search(rf"\b{short}\b", content):
                    content += f"\ntypedef {full} {short};"
            
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if not re.search(rf"\b{tag}\b", content):
                    content = self.strip_redefinition(content, tag)
                    content += f"\n{body}\n"

        if file_path.endswith(('.c', '.cpp')):
            # 1. POSIX Renaming for functions that clash with Android headers
            for name in self.POSIX_RESERVED_NAMES:
                if f" {name}(" in content and f"#define {name}" not in content:
                    prefix = os.path.basename(file_path).split('.')[0]
                    content = f'#define {name} n64_{prefix}_{name}\n' + content

            # 2. Actor context injection
            if "this" in content and "Actor *actor =" not in content and "actor->" in content:
                content = re.sub(r'(\w+::\w+\(.*\)\s*\{)', r'\1\n    Actor *actor = (Actor *)this;', content)

            # 3. Context register access fixes
            content = re.sub(r'->context\.([a-z0-9_]+)', r'->context.regs.\1', content)
            content = re.sub(
                r'\(\s*uint32_t\s*\*\s*\)__osRunningThread->context',
                '((uint32_t*)&__osRunningThread->context.force_align[0])',
                content
            )

        if content != original:
            self.write_file(file_path, content)
            return 1
        return 0
