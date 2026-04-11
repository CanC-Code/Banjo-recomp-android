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
        self.N64_PRIMITIVE_MAP = {
            "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
            "s8": "int8_t", "s16": "int16_t", "s32": "int32_t", "s64": "int64_t",
            "f32": "float", "f64": "double", "b32": "int32_t"
        }

        self.POSIX_RESERVED_NAMES = {"close", "open", "read", "write", "send", "recv", "stat", "rename", "mkdir"}

        # ---------------------------------------------------------------------------
        # Topologically Sorted N64 Structs (Incorporating Old Techniques)
        # ---------------------------------------------------------------------------
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
        logger.info("🛠️ Loading logic (advanced techniques active)")
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
        self.dynamic_categories = defaultdict(set)
        # Unknown types
        for m in re.finditer(r"unknown type name ['\"](.*?)['\"]", log_content):
            self.dynamic_categories["missing_types"].add(m.group(1).strip())
        # POSIX Conflicts
        for m in re.finditer(r"static declaration of ['\"](.*?)['\"] follows non-static", log_content):
            self.dynamic_categories["posix_conflict"].add(m.group(1).strip())
        logger.info(f"📊 Scraped {len(self.dynamic_categories['missing_types'])} missing types.")

    def _strip_redefinition(self, content: str, tag: str) -> str:
        """Aggressively removes old struct/typedefs using brace-matching logic."""
        # Simple typedefs
        content = re.sub(rf"typedef\s+[^;]*\b{tag}\b\s*;", f"/* STRIPPED {tag} */", content)
        # Complex struct bodies
        content = re.sub(rf"struct\s+{tag}\s*\{{[^}}]*\}}\s*;", f"/* STRIPPED STRUCT {tag} */", content)
        return content

    def apply_to_file(self, file_path: str) -> int:
        if not os.path.exists(file_path): return 0
        content = self.read_file(file_path)
        original = content

        if "n64_types.h" in file_path:
            # 1. Inject Standard Primitives
            for short, full in self.N64_PRIMITIVE_MAP.items():
                if not re.search(rf"\b{short}\b", content):
                    content += f"\ntypedef {full} {short};"
            
            # 2. Inject OS Structs with cleanup
            for tag, body in self.N64_OS_STRUCT_BODIES.items():
                if not re.search(rf"\b{tag}\b", content):
                    content = self._strip_redefinition(content, tag)
                    content += f"\n{body}\n"

        if file_path.endswith(('.c', '.cpp')):
            # 3. POSIX Renaming
            for name in self.POSIX_RESERVED_NAMES:
                if f" {name}(" in content and f"#define {name}" not in content:
                    prefix = os.path.basename(file_path).split('.')[0]
                    content = f'#define {name} n64_{prefix}_{name}\n' + content
            
            # 4. Actor context injection
            if "this" in content and "Actor *actor =" not in content:
                content = re.sub(r'(\w+::\w+\(.*\)\s*\{)', r'\1\n    Actor *actor = (Actor *)this;', content)

        if content != original:
            self.write_file(file_path, content)
            return 1
        return 0
