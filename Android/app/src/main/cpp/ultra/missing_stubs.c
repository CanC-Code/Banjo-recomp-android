// missing_stubs.c
#include <string.h>
#include <stdint.h>

// --- 1. Missing OS/Hardware Functions ---
// These are N64-specific hardware calls that don't exist on Android.
void osWritebackDCache(void *vaddr, int32_t nbytes) {}
void osInvalICache(void *vaddr, int32_t nbytes) {}
void osWriteBackDCacheAll(void) {}
void osSetIntMask(uint32_t mask) {}
void __osInitialize_autodetect(void) {}
void initInterruptTables(void) {}

// Standard C support for older code
void bzero(void *s, size_t n) {
    memset(s, 0, n);
}

// --- 2. Missing Global Variables ---
// These are specific memory addresses the game expects to exist.
int D_803FFE00 = 0;
int D_803FBE00 = 0;
void* gFramebuffers[3] = {0, 0, 0};

// --- 3. Missing Linker Script Symbols ---
// On N64, these represent memory addresses. On Android, we provide 
// dummy integers so the code can at least "point" to something.
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
int gSPL3DEX_fifoTextEnd = 0; // Added as a precaution
