// missing_stubs.c
#include <string.h>
#include <stdint.h>

// Match the N64 internal type for interrupt masks
typedef uint32_t OSIntMask;

// --- 1. Missing OS/Hardware Functions ---
// These now match the signatures found in os_exception.h and os_libc.h exactly.

OSIntMask osSetIntMask(OSIntMask mask) {
    return 0; 
}

void bzero(void *s, int n) {
    memset(s, 0, (size_t)n);
}

void osWritebackDCache(void *vaddr, int32_t nbytes) {}
void osInvalICache(void *vaddr, int32_t nbytes) {}
void osWriteBackDCacheAll(void) {}
void __osInitialize_autodetect(void) {}
void initInterruptTables(void) {}

// --- 2. Missing Global Variables ---
int D_803FFE00 = 0;
int D_803FBE00 = 0;
void* gFramebuffers[3] = {0, 0, 0};

// --- 3. Missing Linker Script Symbols ---
int crc_ROM_START = 0;
int core2_TEXT_START = 0;
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
