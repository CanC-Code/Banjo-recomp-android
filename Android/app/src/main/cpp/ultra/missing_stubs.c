// missing_stubs.c
#include <string.h>
#include <stdint.h>

// Match the N64 internal type for interrupt masks
typedef uint32_t OSIntMask;

// --- 1. Missing OS/Hardware Functions ---

OSIntMask osSetIntMask(OSIntMask mask) { return 0; }
OSIntMask __osDisableInt(void) { return 0; }
void __osRestoreInt(OSIntMask mask) {}

// Standard C memory support for older N64 code
void bzero(void *s, int n) { memset(s, 0, (size_t)n); }
void bcopy(const void *src, void *dest, int n) { memmove(dest, src, (size_t)n); }

// Cache and Hardware Interrupts
void osWritebackDCache(void *vaddr, int32_t nbytes) {}
void osInvalICache(void *vaddr, int32_t nbytes) {}
void osInvalDCache(void *vaddr, int32_t nbytes) {}
void osWriteBackDCacheAll(void) {}
void __osInitialize_autodetect(void) {}
void initInterruptTables(void) {}

// Threading, Timers, and Status Registers
uint32_t osGetCount(void) { return 0; }
uint32_t __osGetSR(void) { return 0; }
uint32_t ___osGetSR(void) { return 0; }
void __osSetSR(uint32_t sr) {}
void __osSetFpcCsr(uint32_t csr) {}
void __osSetCompare(uint32_t val) {}

void __osPopThread(void* q) {}
void __osEnqueueThread(void* q, void* t) {}
void __osCleanupThread(void) {}
void __osDispatchThread(void) {}
void __osEnqueueAndYield(void* q) {}

// TLB (Translation Lookaside Buffer)
void osMapTLBRdb(void) {}
uint32_t __osProbeTLB(void* a) { return 0; }

// --- 2. Math Constants ---
float __libm_qnan_f = 0.0f; // Represents a floating point NaN

// --- 3. Unknown Decompiled Functions ---
int func_8025C29C(void) { return 0; }
int func_80253010(void) { return 0; }
void func_8026A2E0(void) {}

// --- 4. Missing Global Variables & Decompiled Addresses ---
int D_803FFE00 = 0;
int D_803FBE00 = 0;
int D_8000E800 = 0;
int D_8002D500 = 0;
int D_8023DA00 = 0;
int D_803FFE10 = 0;
void* gFramebuffers[3] = {0, 0, 0};

// --- 5. Missing Linker Script Symbols ---
int crc_ROM_START = 0;
int soundfont2ctl_ROM_END = 0;
int soundfont2ctl_ROM_START = 0;
int soundfont2tbl_ROM_START = 0;
int n_aspMainTextStart = 0;
int n_aspMainDataStart = 0;
int gSPF3DEX_fifoTextStart = 0;
int gSPF3DEX_fifoDataStart = 0;
int gSPL3DEX_fifoTextStart = 0;
int gSPL3DEX_fifoDataStart = 0;
int gSPL3DEX_fifoTextEnd = 0;

// --- 6. Overlay Memory Boundaries ---

// A C-Macro to easily define all 10 memory boundary variables for any given level
#define DEFINE_OVERLAY(name) \
    int name##_VRAM = 0; \
    int name##_VRAM_END = 0; \
    int name##_ROM_START = 0; \
    int name##_ROM_END = 0; \
    int name##_TEXT_START = 0; \
    int name##_TEXT_END = 0; \
    int name##_DATA_START = 0; \
    int name##_RODATA_END = 0; \
    int name##_BSS_START = 0; \
    int name##_BSS_END = 0;

// Core Engine Overlays
DEFINE_OVERLAY(core2)

// Level Overlays
DEFINE_OVERLAY(emptyLvl)
DEFINE_OVERLAY(SM)          // Spiral Mountain
DEFINE_OVERLAY(MM)          // Mumbo's Mountain
DEFINE_OVERLAY(TTC)         // Treasure Trove Cove
DEFINE_OVERLAY(CC)          // Clanker's Cavern
DEFINE_OVERLAY(BGS)         // Bubblegloop Swamp
DEFINE_OVERLAY(FP)          // Freezeezy Peak
DEFINE_OVERLAY(GV)          // Gobi's Valley
DEFINE_OVERLAY(MMM)         // Mad Monster Mansion
DEFINE_OVERLAY(RBB)         // Rusty Bucket Bay
DEFINE_OVERLAY(CCW)         // Click Clock Wood
DEFINE_OVERLAY(lair)        // Gruntilda's Lair
DEFINE_OVERLAY(fight)       // Final Battle
DEFINE_OVERLAY(cutscenes)   // Intro/Outro Cutscenes
