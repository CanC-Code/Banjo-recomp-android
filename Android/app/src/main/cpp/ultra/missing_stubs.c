// missing_stubs.c
// This file provides dummy C implementations for N64 hardware functions
// and fake memory addresses for variables usually provided by the N64 linker.

#include <string.h>

// --- Standard OS and C Library Functions ---
// The Android NDK often deprecates bzero in favor of memset.
void bzero(void *s, size_t n) {
    memset(s, 0, n);
}

// Dummy N64 hardware cache and interrupt functions
void osWritebackDCache(void *vaddr, int nbytes) {}
void osInvalICache(void *vaddr, int nbytes) {}
void osWriteBackDCacheAll(void) {}
void osSetIntMask(unsigned int mask) {}
void __osInitialize_autodetect(void) {}

// --- Missing Global Variables ---
// The original game expects these to exist in memory
int D_803FFE00 = 0;
int D_803FBE00 = 0;
void* gFramebuffers[3] = {0, 0, 0}; // Array of pointers for N64 framebuffers

// --- Linker Script Addresses ---
// The original game uses these to find the start/end of ROM segments.
// We just define them as generic integers so the compiler has an address to reference.
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
