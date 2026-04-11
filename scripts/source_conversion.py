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

        # Map common N64 primitives to standard C types to prevent bit-field errors
        self.N64_PRIMITIVE_MAP = {
            "u8": "uint8_t",
            "u16": "uint16_t",
            "u32": "uint32_t",
            "u64": "uint64_t",
            "s8": "int8_t",
            "s16": "int16_t",
            "s32": "int32_t",
            "s64": "int64_t",
            "f32": "float",
            "f64": "double",
            "b32": "int32_t",
            "f32": "float"
        }

        # Core N64 OS types. Note the order and use of proper typedefs.
        self.N64_OS_STRUCT_BODIES = {
            "OSThread": """
typedef union __OSThreadContext_u {
    struct {
        uint64_t pc; uint64_t a0; uint64_t sp; uint64_t ra;
        uint32_t sr; uint32_t rcp; uint32_t fpcsr;
    } regs;
    long long int force_align[67];
} __OSThreadContext;

typedef struct OSThread_s {
    struct OSThread_s *next;
    int32_t priority;
    struct OSThread_s **queue;
    struct OSThread_s *tlnext;
    uint16_t state;
    uint16_t flags;
    uint64_t id;
    int fp;
    __OSThreadContext context;
} OSThread;""",
            "OSMesg": "typedef void *OSMesg;",
            "OSTime": "typedef uint64_t OSTime;",
            "OSMesgQueue": """
typedef struct OSMesgQueue_s {
    struct OSThread_s *mtqueue;
    struct OSThread_s *fullqueue;
    int32_t validCount;
    int32_t first;
    int32_t msgCount;
    OSMesg *msg;
} OSMesgQueue;""",
            "OSMesgHdr": "typedef struct { uint16_t type; uint8_t pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
            "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; } OSPiHandle;",
        }

    def load_logic(self):
        logger.info("🛠️ Loading conversion logic (internal rules active)")
        return True

    def read_file(self, file_path: str) -> str:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""

    def write_file(self, file_path: str, content: str):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def scrape_logs(self, log_content: str):
        self.dynamic_categories = defaultdict(set)
        for m in re.finditer(r"unknown type name ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["missing_types"].add(m.group(1).strip())
        for m in re.finditer(r"use of undeclared identifier ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["undeclared_identifiers"].add(m.group(1).strip())
        logger.info(f"📊 Scraped {len(self.dynamic_categories['missing_types'])} missing types.")

    def apply_dynamic_fixes(self):
        if not os.path.exists(self.types_header):
            return

        content = self.read_file(self.types_header)
        updated = False

        for typ in self.dynamic_categories.get("missing_types", set()):
            # Use word boundary check to avoid redundant definitions
            if not re.search(rf"\b{typ}\b", content):
                if typ in self.N64_PRIMITIVE_MAP:
                    content += f"\ntypedef {self.N64_PRIMITIVE_MAP[typ]} {typ};"
                else:
                    # Default unknown types to opaque structs instead of void*
                    # This is safer for pointers but still avoids bit-field issues
                    content += f"\ntypedef struct {typ}_s {typ};"
                updated = True
        
        if updated:
            self.write_file(self.types_header, content)
            logger.info("🩹 Applied dynamic fixes to n64_types.h")

    def _inject_essentials(self, content: str) -> str:
        """Prepends standard headers to the top of the file."""
        headers = [
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "#include <stddef.h>"
        ]
        
        # Insert after #pragma once if it exists, otherwise at the top
        insert_pos = 0
        pragma_match = re.search(r"#pragma\s+once", content)
        if pragma_match:
            insert_pos = pragma_match.end()

        for header in reversed(headers):
            if header not in content:
                content = content[:insert_pos] + f"\n{header}" + content[insert_pos:]
        
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        
        content = self.read_file(file_path)
        original = content

        if "n64_types.h" in file_path:
            content = self._inject_essentials(content)
            
            # Inject N64 Primitives first
            for short, full in self.N64_PRIMITIVE_MAP.items():
                if not re.search(rf"\b{short}\b", content):
                    content += f"\ntypedef {full} {short};"

            # Inject core OS structs using whole-word matching
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                # Check for tag as a whole word (e.g., 'OSThread')
                if not re.search(rf"\b{tag}\b", content):
                    content += f"\n{body}\n"

        if file_path.endswith(('.c', '.cpp')):
            # Fix context register access
            content = re.sub(r'->context\.([a-z0-9_]+)', r'->context.regs.\1', content)
            # Fix raw memory casts for registers
            content = re.sub(
                r'\(\s*uint32_t\s*\*\s*\)__osRunningThread->context',
                '((uint32_t*)&__osRunningThread->context.force_align[0])',
                content
            )

        if content != original:
            self.write_file(file_path, content)
            return 1
        return 0
