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
        
        # Track dynamic findings from logs
        self.dynamic_categories = defaultdict(set)

        # Core N64 OS types that must exist
        self.N64_OS_STRUCT_BODIES = {
            "OSMesgQueue": "typedef struct OSMesgQueue_s { struct OSThread_s *mtqueue; struct OSThread_s *fullqueue; int32_t validCount; int32_t first; int32_t msgCount; OSMesg *msg; } OSMesgQueue;",
            "OSThread": """typedef union __OSThreadContext_u { struct { uint64_t pc; uint64_t a0; uint64_t sp; uint64_t ra; uint32_t sr; uint32_t rcp; uint32_t fpcsr; } regs; long long int force_align[67]; } __OSThreadContext; typedef struct OSThread_s { struct OSThread_s *next; int32_t priority; struct OSThread_s **queue; struct OSThread_s *tlnext; uint16_t state; uint16_t flags; uint64_t id; int fp; __OSThreadContext context; } OSThread;""",
            "OSMesgHdr": "typedef struct { uint16_t type; uint8_t pri; struct OSMesgQueue_s *retQueue; } OSMesgHdr;",
            "OSPiHandle": "typedef struct OSPiHandle_s { struct OSPiHandle_s *next; uint8_t type; uint8_t latency; uint8_t pageSize; uint8_t relDuration; uint8_t pulse; uint8_t domain; uint32_t baseAddress; uint32_t speed; } OSPiHandle;",
        }

    def load_logic(self):
        """Required by build_driver.py: Initializes internal rules."""
        logger.info("🛠️ Loading conversion logic (internal rules active)")
        # If you add external JSON/YAML rules later, they get loaded here.
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
        """Analyzes build log for missing types and identifiers."""
        self.dynamic_categories = defaultdict(set)
        
        # Find unknown types
        for m in re.finditer(r"unknown type name ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["missing_types"].add(m.group(1).strip())
            
        # Find undeclared identifiers
        for m in re.finditer(r"use of undeclared identifier ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["undeclared_identifiers"].add(m.group(1).strip())
        
        logger.info(f"📊 Scraped {len(self.dynamic_categories['missing_types'])} missing types from log.")

    def apply_dynamic_fixes(self):
        """Injects findings from scrape_logs into the types header."""
        if not os.path.exists(self.types_header):
            return

        content = self.read_file(self.types_header)
        updated = False

        for typ in self.dynamic_categories.get("missing_types", set()):
            if typ not in content and typ not in ["uint64_t", "int32_t", "uint16_t", "uint8_t"]:
                content += f"\ntypedef void* {typ}; /* Dynamically fixed */"
                updated = True
        
        if updated:
            self.write_file(self.types_header, content)
            logger.info("🩹 Applied dynamic fixes to n64_types.h")

    def _inject_essentials(self, content: str) -> str:
        """Ensures standard headers and basic N64 primitives exist."""
        essentials = [
            "#include <stdint.h>",
            "#include <stdbool.h>",
            "#include <stddef.h>",
            "typedef void* OSMesg;",
            "typedef uint64_t OSTime;",
            "typedef int32_t s32;",
            "typedef uint32_t u32;"
        ]
        
        for item in essentials:
            # Check for the type/include without getting tripped up by similar names
            pattern = rf"{re.escape(item)}"
            if not re.search(pattern, content):
                content = content.strip() + f"\n{item}\n"
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            return 0
        
        content = self.read_file(file_path)
        original = content

        # Special handling for the core types header
        if "n64_types.h" in file_path:
            content = self._inject_essentials(content)
            
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if tag not in content:
                    content += f"\n{body}\n"

        # Apply specific fixes for ASM/Register access in source files
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
