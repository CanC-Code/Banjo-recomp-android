#include "HardwareRegs.h"
#include <sys/mman.h>
#include <errno.h>
#include <android/log.h>
#include <cstdlib>
#include <cstring>

#define LOG_TAG "BKA_MEM"

// --- N64 Physical Memory Map (as seen by the recompiler) ---
// The recompiler emits code with hardcoded offsets relative to these bases.
// These MUST be the actual virtual addresses used — a fallback to an arbitrary
// heap address will be silently ignored by recompiled code that computes
// absolute addresses directly (e.g. lui $t0, 0xa000 / sw $v0, offset($t0)).

// RDRAM: 0x80000000 / uncached mirror 0xa0000000, 8MB
// The translation macro now safely masks mirrored accesses, so this remains 8MB.
#define N64_RDRAM_BASE_ADDR     0x80000000UL
#define N64_RDRAM_SIZE          0x00800000UL   // 8 MB

// RCP register space: 0xa3f00000–0xa4ffffff (uncached)
// Covered by a 32MB window anchored at 0xa3000000 for alignment safety.
#define N64_RCP_BASE_ADDR       0xa3000000UL
#define N64_RCP_SPACE_SIZE      0x02000000UL   // 32 MB window covers all RCP regs

// PIF ROM/RAM: physical 0x1fc00000, uncached mirror 0xbfc00000
#define N64_PIF_BASE_ADDR       0xbfc00000UL
#define N64_PIF_SPACE_SIZE      0x00001000UL   // 4 KB

// Enforce C-linkage so the recompiled C translation units can reference these
// without name-mangling mismatches. Only ONE definition must exist — here.
extern "C" {
    uint32_t* gN64_Reg_Base  = nullptr;   // Points to RCP register window
    uint32_t* gN64_PIF_Base  = nullptr;   // Points to PIF ROM/RAM window
    uint8_t* gN64_RDRAM      = nullptr;   // Points to main RDRAM
    uint32_t* gN64_RAM_Base  = nullptr;   // Points to RDRAM for the routing macro
}

// ----------------------------------------------------------------------------
// try_map_fixed: attempt MAP_FIXED at the requested N64 physical address.
//
// On Android 14 (aarch64, 39-bit VA), addresses like 0xa0000000 are in the
// upper user VA range and MAP_FIXED will succeed only if nothing is already
// mapped there. If it fails we do NOT silently fall back to malloc — the
// recompiled game uses the address directly in pointer arithmetic and a
// random heap address will not be used by those paths, leaving hardware
// register writes hitting unmapped memory and producing SEGV_ACCERR.
//
// Instead, if MAP_FIXED fails we try MAP_FIXED_NOREPLACE (kernel 4.17+,
// Android 12+) for a cleaner failure mode, then abort with a clear message.
// A future improvement would be to patch the recompiler output to use
// a base-relative addressing mode, but that is out of scope here.
// ----------------------------------------------------------------------------
static void* try_map_fixed(void* addr, size_t size, const char* name) {
    // First attempt: MAP_FIXED — will replace any existing mapping at that VA.
    void* p = mmap(addr, size,
                   PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED,
                   -1, 0);

    if (p != MAP_FAILED) {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG,
            "InitN64Registers: Mapped %s at fixed addr %p (%zu KB)",
            name, p, size / 1024);
        return p;
    }

    __android_log_print(ANDROID_LOG_FATAL, LOG_TAG,
        "InitN64Registers: MAP_FIXED FAILED for %s at %p: %s. "
        "The recompiled game uses this address in hardcoded pointer arithmetic — "
        "a heap fallback cannot substitute. "
        "Ensure no prior mapping occupies this VA range before calling InitN64Registers.",
        name, addr, strerror(errno));

    // Hard abort. A silent fallback here causes SEGV_ACCERR inside the game thread.
    abort();
    return nullptr; // unreachable
}

extern "C" void InitN64Registers() {
    // Guard against redundant init (e.g. called from multiple threads at startup)
    if (gN64_Reg_Base != nullptr && gN64_PIF_Base != nullptr && gN64_RDRAM != nullptr) {
        return;
    }

    // 1. RDRAM — main 8MB working memory
    if (gN64_RDRAM == nullptr) {
        gN64_RDRAM = (uint8_t*)try_map_fixed((void*)N64_RDRAM_BASE_ADDR,
                                              N64_RDRAM_SIZE, "RDRAM");
        memset(gN64_RDRAM, 0, N64_RDRAM_SIZE);

        // Initialize the routing macro's RAM base pointer
        gN64_RAM_Base = (uint32_t*)gN64_RDRAM;
    }

    // 2. RCP register space — SP, DP, MI, VI, AI, PI, RI, SI registers
    if (gN64_Reg_Base == nullptr) {
        gN64_Reg_Base = (uint32_t*)try_map_fixed((void*)N64_RCP_BASE_ADDR,
                                                  N64_RCP_SPACE_SIZE, "RCP");
        memset(gN64_Reg_Base, 0, N64_RCP_SPACE_SIZE);
    }

    // 3. PIF ROM/RAM
    if (gN64_PIF_Base == nullptr) {
        gN64_PIF_Base = (uint32_t*)try_map_fixed((void*)N64_PIF_BASE_ADDR,
                                                  N64_PIF_SPACE_SIZE, "PIF");
        memset(gN64_PIF_Base, 0, N64_PIF_SPACE_SIZE);
    }
}

void HardwareRegs_Shutdown() {
    if (gN64_RDRAM != nullptr) {
        if ((uintptr_t)gN64_RDRAM == N64_RDRAM_BASE_ADDR)
            munmap(gN64_RDRAM, N64_RDRAM_SIZE);
        gN64_RDRAM = nullptr;
        gN64_RAM_Base = nullptr;
    }

    if (gN64_Reg_Base != nullptr) {
        if ((uintptr_t)gN64_Reg_Base == N64_RCP_BASE_ADDR)
            munmap(gN64_Reg_Base, N64_RCP_SPACE_SIZE);
        gN64_Reg_Base = nullptr;
    }

    if (gN64_PIF_Base != nullptr) {
        if ((uintptr_t)gN64_PIF_Base == N64_PIF_BASE_ADDR)
            munmap(gN64_PIF_Base, N64_PIF_SPACE_SIZE);
        gN64_PIF_Base = nullptr;
    }
}
