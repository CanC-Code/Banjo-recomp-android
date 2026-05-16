#pragma once
/*
 * bka_safe_base.h  –  BKA Android N64 address translation layer
 *
 * THREAD SAFETY
 * ─────────────
 * Base memory pointers are written once during InitN64Registers() which MUST be
 * called from the JNI init path before BKA-GameThread is spawned.
 * BKA_Validate_And_Translate uses an atomic load with acquire semantics
 * as a secondary safety net.
 *
 * RDRAM SIZE
 * ──────────
 * The physical N64 RDRAM is 8 MB (0x800000).  The decompiled code may
 * perform speculative over-reads up to address 0x800018 and beyond.
 * gN64_RDRAM must therefore be allocated as at least 16 MB (0x1000000).
 */

#include <android/log.h>
#include <stdint.h>

#define BKA_RDRAM_ALLOC_SIZE  (0x1000000u)   /* 16 MB – covers 0x800018 over-reads */
#define BKA_RDRAM_PHYS_SIZE   (0x800000u)    /* 8 MB  – original N64 RDRAM           */

#ifdef __cplusplus
extern "C" {
#endif

/*
 * These globals are written ONCE by InitN64Registers() before any
 * game thread starts. Reads from the game thread use acquire-load so
 * the processor cannot speculate past the initialisation write.
 */
extern uint8_t* gN64_RDRAM;
extern uint32_t* gN64_Reg_Base;
extern uint32_t* gN64_PIF_Base;
extern uint8_t* gN64_ROM_Base;

extern void InitN64Registers(void);

#ifdef __cplusplus
}
#endif

/* ── Address translation ──────────────────────────────────────────────── */

static inline uintptr_t BKA_Validate_And_Translate(
        uintptr_t addr, const char* file, int line)
{
    uint32_t mask32 = (uint32_t)(addr & 0xFFFFFFFFu);

    if (mask32 == 0u) return 0u;

    /* Pass through genuine 64-bit host pointers unchanged. */
    if ((addr >> 32) != 0u && (addr >> 32) != 0xFFFFFFFFu) return addr;

    /*
     * Acquire-load: Ensures visibility of InitN64Registers() writes.
     * Compiler built-ins strictly avoid standard library <stdatomic.h> imports.
     */
    uint8_t* ram_ptr = __atomic_load_n(&gN64_RDRAM,    __ATOMIC_ACQUIRE);
    uint32_t* reg_ptr = __atomic_load_n(&gN64_Reg_Base, __ATOMIC_ACQUIRE);
    uint32_t* pif_ptr = __atomic_load_n(&gN64_PIF_Base, __ATOMIC_ACQUIRE);
    uint8_t* rom_ptr = __atomic_load_n(&gN64_ROM_Base, __ATOMIC_ACQUIRE);

    if (!ram_ptr) {
        __android_log_print(ANDROID_LOG_FATAL, "BKA_MEM_FAULT",
            "[%s:%d] BKA_TRANSLATE_ADDR called before InitN64Registers(). "
            "addr=0x%08x", file, line, mask32);
        return addr;
    }

    uintptr_t ram = (uintptr_t)ram_ptr;
    uintptr_t reg = (uintptr_t)reg_ptr;
    uintptr_t pif = (uintptr_t)pif_ptr;
    uintptr_t rom = (uintptr_t)rom_ptr;

    /* RDRAM – bare physical (0x000000 – 0x0FFFFF) and over-read window */
    if (mask32 < BKA_RDRAM_ALLOC_SIZE)            return ram + mask32;
    /* RDRAM – K0 cached segment  (0x80000000) */
    if (mask32 >= 0x80000000u && mask32 < 0x81000000u)
                                                   return ram + (mask32 - 0x80000000u);
    /* RDRAM – K1 uncached segment (0xA0000000) */
    if (mask32 >= 0xA0000000u && mask32 < 0xA1000000u)
                                                   return ram + (mask32 - 0xA0000000u);
    /* RSP DMEM/IMEM / RCP registers (0x04000000) */
    if (mask32 >= 0x04000000u && mask32 < 0x05000000u)
                                                   return reg + (mask32 - 0x04000000u);
    if (mask32 >= 0xA4000000u && mask32 < 0xA5000000u)
                                                   return reg + (mask32 - 0xA4000000u);
    /* PIF ROM/RAM (0x1FC00000) */
    if (mask32 >= 0x1FC00000u && mask32 < 0x1FC01000u)
                                                   return pif + (mask32 - 0x1FC00000u);
    if (mask32 >= 0xBFC00000u && mask32 < 0xBFC01000u)
                                                   return pif + (mask32 - 0xBFC00000u);
                                                   
    /* Cartridge ROM – Physical (0x10000000) and K1 Uncached (0xB0000000) */
    /* 64MB Boundary Limits: 0x14000000u & 0xB4000000u */
    if (mask32 >= 0x10000000u && mask32 < 0x14000000u)
                                                   return rom + (mask32 - 0x10000000u);
    if (mask32 >= 0xB0000000u && mask32 < 0xB4000000u)
                                                   return rom + (mask32 - 0xB0000000u);

    __android_log_print(ANDROID_LOG_FATAL, "BKA_MEM_FAULT",
        "[%s:%d] UNMAPPED N64 ACCESS: 0x%08x", file, line, mask32);
    return addr;  /* let the real fault happen so tombstone is useful */
}

#define BKA_TRANSLATE_ADDR(addr) \
    BKA_Validate_And_Translate((uintptr_t)(addr), __FILE__, __LINE__)

static inline uintptr_t BKA_Reverse_Addr(uintptr_t addr)
{
    uint8_t* ram_ptr = __atomic_load_n(&gN64_RDRAM,    __ATOMIC_ACQUIRE);
    uint32_t* reg_ptr = __atomic_load_n(&gN64_Reg_Base, __ATOMIC_ACQUIRE);
    uint8_t* rom_ptr = __atomic_load_n(&gN64_ROM_Base, __ATOMIC_ACQUIRE);
    
    if (!ram_ptr) return addr;
    
    uintptr_t ram = (uintptr_t)ram_ptr;
    uintptr_t reg = (uintptr_t)reg_ptr;
    uintptr_t rom = (uintptr_t)rom_ptr;
    
    if (addr >= ram && addr < ram + BKA_RDRAM_ALLOC_SIZE) return addr - ram;
    if (addr >= reg && addr < reg + 0x01000000u) return (addr - reg) + 0x04000000u;
    
    /* 64MB ROM reverse lookup boundary */
    if (addr >= rom && addr < rom + 0x04000000u) return (addr - rom) + 0x10000000u;
    
    return addr;
}
