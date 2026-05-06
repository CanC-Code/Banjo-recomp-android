#include "HardwareRegs.h"
#include <sys/mman.h>
#include <errno.h>
#include <android/log.h>
#include <cstdlib>
#include <cstring>

#define LOG_TAG "BKA_MEM"

// Expanded RDRAM to 16MB to safely capture OOB offset accesses (e.g., 0x800018)
#define N64_RDRAM_BASE_ADDR     0x80000000UL
#define N64_RDRAM_SIZE          0x01000000UL   // 16 MB

#define N64_RCP_BASE_ADDR       0xa3000000UL
#define N64_RCP_SPACE_SIZE      0x02000000UL   // 32 MB 

#define N64_PIF_BASE_ADDR       0xbfc00000UL
#define N64_PIF_SPACE_SIZE      0x00001000UL   // 4 KB

extern "C" {
    uint32_t* gN64_Reg_Base  = nullptr;
    uint32_t* gN64_PIF_Base  = nullptr;
    uint8_t* gN64_RDRAM      = nullptr;
    uint32_t* gN64_RAM_Base  = nullptr;
}

static void* safe_allocate(void* addr, size_t size, const char* name) {
    // Attempt MAP_FIXED to match N64 physical memory addresses directly
    void* p = mmap(addr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);

    if (p != MAP_FAILED) {
        __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Mapped %s at fixed addr %p (%zu KB)", name, p, size / 1024);
        return p;
    }

    __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "MAP_FIXED FAILED for %s at %p. Falling back to dynamic OS allocation.", name, addr);
    
    // Fallback to standard dynamic allocation
    p = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    
    if (p != MAP_FAILED) {
        __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Mapped %s dynamically at %p (%zu KB)", name, p, size / 1024);
        return p;
    }

    __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "CRITICAL: Total allocation failure for %s. Aborting.", name);
    abort();
    return nullptr;
}

extern "C" void InitN64Registers() {
    if (gN64_Reg_Base != nullptr && gN64_PIF_Base != nullptr && gN64_RDRAM != nullptr) {
        return;
    }

    __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Hardware Base Initialization Triggered");

    if (gN64_RDRAM == nullptr) {
        gN64_RDRAM = (uint8_t*)safe_allocate((void*)N64_RDRAM_BASE_ADDR, N64_RDRAM_SIZE, "RDRAM");
        memset(gN64_RDRAM, 0, N64_RDRAM_SIZE);
        gN64_RAM_Base = (uint32_t*)gN64_RDRAM;
    }

    if (gN64_Reg_Base == nullptr) {
        gN64_Reg_Base = (uint32_t*)safe_allocate((void*)N64_RCP_BASE_ADDR, N64_RCP_SPACE_SIZE, "RCP");
        memset(gN64_Reg_Base, 0, N64_RCP_SPACE_SIZE);
    }

    if (gN64_PIF_Base == nullptr) {
        gN64_PIF_Base = (uint32_t*)safe_allocate((void*)N64_PIF_BASE_ADDR, N64_PIF_SPACE_SIZE, "PIF");
        memset(gN64_PIF_Base, 0, N64_PIF_SPACE_SIZE);
    }
}

void HardwareRegs_Shutdown() {
    if (gN64_RDRAM != nullptr) {
        munmap(gN64_RDRAM, N64_RDRAM_SIZE);
        gN64_RDRAM = nullptr;
        gN64_RAM_Base = nullptr;
    }

    if (gN64_Reg_Base != nullptr) {
        munmap(gN64_Reg_Base, N64_RCP_SPACE_SIZE);
        gN64_Reg_Base = nullptr;
    }

    if (gN64_PIF_Base != nullptr) {
        munmap(gN64_PIF_Base, N64_PIF_SPACE_SIZE);
        gN64_PIF_Base = nullptr;
    }
}
