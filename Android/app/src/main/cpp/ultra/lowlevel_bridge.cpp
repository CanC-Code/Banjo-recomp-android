#include "HardwareRegs.h"
#include <sys/mman.h>
#include <errno.h>
#include <android/log.h>
#include <cstdlib>
#include <cstring>

#define LOG_TAG "BKA_MEM"
#define RECOMP_BASE_ADDR 0xa0000000 
#define N64_REG_SPACE_SIZE 0x1000000 // 16MB

// Define the global pointer
uint32_t* gN64_Reg_Base = nullptr;

extern "C" void InitN64Registers() {
    if (gN64_Reg_Base != nullptr) {
        return;
    }

    void* fixed_addr = (void*)RECOMP_BASE_ADDR;
    
    // Attempt to map exactly at 0xa0000000 to satisfy hardcoded recompilation pointers
    gN64_Reg_Base = (uint32_t*)mmap(
        fixed_addr, 
        N64_REG_SPACE_SIZE, 
        PROT_READ | PROT_WRITE, 
        MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
        -1, 0
    );

    if (gN64_Reg_Base == MAP_FAILED) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, 
            "MAP_FIXED failed at %p: %s. Switching to fallback.", fixed_addr, strerror(errno));
        
        // Fallback: Allocate memory anywhere in the heap if the fixed address is blocked
        gN64_Reg_Base = (uint32_t*)malloc(N64_REG_SPACE_SIZE);
        
        if (gN64_Reg_Base == nullptr) {
            __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Critical memory allocation failure.");
            abort();
        }
    } else {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG, 
            "Successfully mapped N64 space at fixed address %p", gN64_Reg_Base);
    }

    // Always zero out the register space on initialization
    memset(gN64_Reg_Base, 0, N64_REG_SPACE_SIZE);
}

void HardwareRegs_Shutdown() {
    if (gN64_Reg_Base != nullptr) {
        // Check if it was an mmap or a malloc
        // Note: For simplicity, if RECOMP_BASE_ADDR is consistent, we munmap
        if ((uintptr_t)gN64_Reg_Base == RECOMP_BASE_ADDR) {
            munmap(gN64_Reg_Base, N64_REG_SPACE_SIZE);
        } else {
            free(gN64_Reg_Base);
        }
        gN64_Reg_Base = nullptr;
    }
}
