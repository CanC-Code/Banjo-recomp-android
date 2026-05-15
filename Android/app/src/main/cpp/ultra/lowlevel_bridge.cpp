#include <sys/mman.h>
#include <errno.h>
#include <android/log.h>
#include <cstdlib>
#include <cstring>
#include <stdint.h>

#define LOG_TAG "BKA_MEM"

// Size allocations matching the expectations of bka_safe_base.h
#define BKA_RDRAM_ALLOC_SIZE  0x1000000 // 16MB (Covers speculative over-reads)
#define N64_REG_SPACE_SIZE    0x1000000 // 16MB (Covers RCP/RCP register ranges)
#define N64_PIF_SPACE_SIZE    0x0010000 // 64KB (Abundantly covers PIF ROM/RAM)

// Instantiate the global translation pointers defined as externs by the sanitizer
uint8_t*  gN64_RDRAM    = nullptr;
uint32_t* gN64_Reg_Base = nullptr;
uint32_t* gN64_PIF_Base = nullptr;

extern "C" void InitN64Registers() {
    // Idempotency guard: Prevent double allocation if called repeatedly
    if (gN64_RDRAM != nullptr && gN64_Reg_Base != nullptr && gN64_PIF_Base != nullptr) {
        return;
    }

    // 1. Allocate Main N64 RDRAM Memory Space
    gN64_RDRAM = (uint8_t*)mmap(
        nullptr, 
        BKA_RDRAM_ALLOC_SIZE, 
        PROT_READ | PROT_WRITE, 
        MAP_PRIVATE | MAP_ANONYMOUS, 
        -1, 0
    );

    // 2. Allocate N64 Hardware Emulation Register Space
    gN64_Reg_Base = (uint32_t*)mmap(
        nullptr, 
        N64_REG_SPACE_SIZE, 
        PROT_READ | PROT_WRITE, 
        MAP_PRIVATE | MAP_ANONYMOUS, 
        -1, 0
    );

    // 3. Allocate N64 PIF Subsystem Memory Space
    gN64_PIF_Base = (uint32_t*)mmap(
        nullptr, 
        N64_PIF_SPACE_SIZE, 
        PROT_READ | PROT_WRITE, 
        MAP_PRIVATE | MAP_ANONYMOUS, 
        -1, 0
    );

    // Hard Fail Verification: Ensure the Android kernel granted all three spaces securely
    if (gN64_RDRAM == MAP_FAILED || gN64_Reg_Base == MAP_FAILED || gN64_PIF_Base == MAP_FAILED) {
        __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, 
            "Critical virtual memory mapping failure: %s", strerror(errno));
        
        // Cleanup any partial allocations before panicking
        if (gN64_RDRAM    != MAP_FAILED && gN64_RDRAM    != nullptr) munmap(gN64_RDRAM,    BKA_RDRAM_ALLOC_SIZE);
        if (gN64_Reg_Base != MAP_FAILED && gN64_Reg_Base != nullptr) munmap(gN64_Reg_Base, N64_REG_SPACE_SIZE);
        if (gN64_PIF_Base != MAP_FAILED && gN64_PIF_Base != nullptr) munmap(gN64_PIF_Base, N64_PIF_SPACE_SIZE);
        
        gN64_RDRAM    = nullptr;
        gN64_Reg_Base = nullptr;
        gN64_PIF_Base = nullptr;
        abort();
    }

    // Zero out all allocated pools to guarantee clean emulation states
    memset(gN64_RDRAM,    0, BKA_RDRAM_ALLOC_SIZE);
    memset(gN64_Reg_Base, 0, N64_REG_SPACE_SIZE);
    memset(gN64_PIF_Base, 0, N64_PIF_SPACE_SIZE);

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, 
        "Memory Engine Stabilized: RDRAM Base=%p, Reg Base=%p, PIF Base=%p", 
        gN64_RDRAM, gN64_Reg_Base, gN64_PIF_Base);
}

void HardwareRegs_Shutdown() {
    if (gN64_RDRAM != nullptr) {
        munmap(gN64_RDRAM, BKA_RDRAM_ALLOC_SIZE);
        gN64_RDRAM = nullptr;
    }
    if (gN64_Reg_Base != nullptr) {
        munmap(gN64_Reg_Base, N64_REG_SPACE_SIZE);
        gN64_Reg_Base = nullptr;
    }
    if (gN64_PIF_Base != nullptr) {
        munmap(gN64_PIF_Base, N64_PIF_SPACE_SIZE);
        gN64_PIF_Base = nullptr;
    }
    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Memory Engine Closed down cleanly.");
}
