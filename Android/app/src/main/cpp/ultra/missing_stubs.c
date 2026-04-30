// missing_stubs.c
//
// LAST-RESORT fallbacks only.
//
// Rules:
//   - Do NOT define anything that has a real implementation in:
//       exceptasm.cpp    (initInterruptTables, __osPopThread, __osEnqueueThread,
//                         __osDispatchThread, __osEnqueueAndYield)
//       setintmask.cpp   (osSetIntMask)
//       libm_vals.cpp    (__libm_qnan_f)
//       lowlevel_bridge.cpp (osPiReadIo, osPiWriteIo)
//       audio_bridge.cpp (n_alSynAddPlayer, n_alSynRemovePlayer, etc.)
//       stubs.cpp        (initInterruptTables fallback, stub_void, etc.)
//
//   CMakeLists.txt lists this file LAST so the linker always prefers
//   the real implementations above when --allow-multiple-definition is set.

#include <string.h>
#include <stdint.h>

typedef uint32_t OSIntMask;

// -----------------------------------------------------------------------
// OS / Hardware — only stubs not covered by any other translation unit
// -----------------------------------------------------------------------

// __osDisableInt / __osRestoreInt: no real impl elsewhere
OSIntMask __osDisableInt(void) { return 0; }
void      __osRestoreInt(OSIntMask mask) { (void)mask; }

// Standard BSD memory aliases used by old N64 SDK code
void bzero(void *s, int n)                    { memset(s, 0, (size_t)n); }
void bcopy(const void *src, void *dest, int n){ memmove(dest, src, (size_t)n); }

// Cache invalidation — no-ops on Android (cache is coherent from the CPU side)
void osWritebackDCache(void *vaddr, int32_t nbytes)  { (void)vaddr; (void)nbytes; }
void osInvalICache(void *vaddr, int32_t nbytes)       { (void)vaddr; (void)nbytes; }
void osInvalDCache(void *vaddr, int32_t nbytes)       { (void)vaddr; (void)nbytes; }
void osWriteBackDCacheAll(void)                       {}
void __osInitialize_autodetect(void)                  {}

// Thread helpers not covered by exceptasm.cpp
void __osCleanupThread(void) {}

// Timer / coprocessor registers — no real impl
uint32_t osGetCount(void)              { return 0; }
uint32_t __osGetSR(void)               { return 0; }
uint32_t ___osGetSR(void)              { return 0; }
void     __osSetSR(uint32_t sr)        { (void)sr; }
void     __osSetFpcCsr(uint32_t csr)   { (void)csr; }
void     __osSetCompare(uint32_t val)  { (void)val; }

// TLB — no-ops on Android
void     osMapTLBRdb(void)             {}
uint32_t __osProbeTLB(void* a)         { (void)a; return 0; }

// -----------------------------------------------------------------------
// Unknown decompiled functions
// -----------------------------------------------------------------------
int  func_8025C29C(void) { return 0; }
int  func_80253010(void) { return 0; }
int  func_80253034(void) { return 0; }
void func_8026A2E0(void) {}

// -----------------------------------------------------------------------
// Missing global variables & decompiled addresses
// -----------------------------------------------------------------------
int   D_803FFE00  = 0;
int   D_803FBE00  = 0;
int   D_8000E800  = 0;
int   D_8002D500  = 0;
int   D_8023DA00  = 0;
int   D_803FFE10  = 0;
void* gFramebuffers[3] = {0, 0, 0};

// -----------------------------------------------------------------------
// Linker script symbols (ROM region boundaries)
// -----------------------------------------------------------------------
int crc_ROM_START            = 0;
int soundfont1ctl_ROM_START  = 0;
int soundfont1ctl_ROM_END    = 0;
int soundfont1tbl_ROM_START  = 0;
int soundfont2ctl_ROM_START  = 0;
int soundfont2ctl_ROM_END    = 0;
int soundfont2tbl_ROM_START  = 0;
int assets_ROM_START         = 0;
int boot_bk_boot_ROM_START   = 0;
int boot_bk_boot_ROM_END     = 0;
int n_aspMainTextStart        = 0;
int n_aspMainDataStart        = 0;
int gSPF3DEX_fifoTextStart   = 0;
int gSPF3DEX_fifoDataStart   = 0;
int gSPL3DEX_fifoTextStart   = 0;
int gSPL3DEX_fifoDataStart   = 0;
int gSPL3DEX_fifoTextEnd     = 0;

// -----------------------------------------------------------------------
// Overlay memory boundaries
// -----------------------------------------------------------------------
#define DEFINE_OVERLAY(name) \
    int name##_VRAM        = 0; \
    int name##_VRAM_END    = 0; \
    int name##_ROM_START   = 0; \
    int name##_ROM_END     = 0; \
    int name##_TEXT_START  = 0; \
    int name##_TEXT_END    = 0; \
    int name##_DATA_START  = 0; \
    int name##_RODATA_END  = 0; \
    int name##_BSS_START   = 0; \
    int name##_BSS_END     = 0;

DEFINE_OVERLAY(core2)
DEFINE_OVERLAY(emptyLvl)
DEFINE_OVERLAY(SM)
DEFINE_OVERLAY(MM)
DEFINE_OVERLAY(TTC)
DEFINE_OVERLAY(CC)
DEFINE_OVERLAY(BGS)
DEFINE_OVERLAY(FP)
DEFINE_OVERLAY(GV)
DEFINE_OVERLAY(MMM)
DEFINE_OVERLAY(RBB)
DEFINE_OVERLAY(CCW)
DEFINE_OVERLAY(lair)
DEFINE_OVERLAY(fight)
DEFINE_OVERLAY(cutscenes)
