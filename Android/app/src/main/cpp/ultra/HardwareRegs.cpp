#include "HardwareRegs.h"
#include <sys/mman.h>
#include <errno.h>
#include <android/log.h>
#include <cstdlib>
#include <cstring>

#define LOG_TAG "BKA_MEM"

// The RCP registers live between 0x04000000 and 0x04FFFFFF in physical N64 memory.
// In K1 (Uncached) virtual memory space, this corresponds to a base of 0xA4000000.
#define N64_K1_RCP_BASE_ADDR 0xA4000000 
#define N64_RCP_SPACE_SIZE 0x01000000 // 16MB to safely cover SP through SI

uint32_t* gN64_Reg_Base = nullptr;

static void* aligned_malloc(size_t alignment, size_t size) {
    void* ptr = nullptr;

    // alignment must be multiple of sizeof(void*)
    if (alignment < sizeof(void*)) {
        alignment = sizeof(void*);
    }

    if (posix_memalign(&ptr, alignment, size) != 0) {
        return nullptr;
    }

    return ptr;
}

static void aligned_free(void* ptr) {
    free(ptr);
}

extern "C" void InitN64Registers() {
    if (gN64_Reg_Base != nullptr) {
        return;
    }

    void* target_addr = (void*)N64_K1_RCP_BASE_ADDR;
    
    // Attempt to map exactly at 0xA4000000 to satisfy hardcoded recompilation pointers
    // The crashing address 0xa4800018 falls safely within this 16MB block.
    gN64_Reg_Base = (uint32_t*)mmap(
        target_addr, 
        N64_RCP_SPACE_SIZE, 
        PROT_READ | PROT_WRITE, 
        MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, 
        -1, 0
    );

    if (gN64_Reg_Base == MAP_FAILED) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, 
            "MAP_FIXED failed at %p: %s. Switching to fallback.", target_addr, strerror(errno));
        
        // Fallback: Allocate memory using the previously established aligned_malloc
        gN64_Reg_Base = (uint32_t*)aligned_malloc(16, N64_RCP_SPACE_SIZE);
        
        if (gN64_Reg_Base == nullptr) {
            __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Critical memory allocation failure.");
            abort();
        }
    } else {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG, 
            "Successfully mapped RCP space at fixed address %p", gN64_Reg_Base);
    }

    // Always zero out the register space on initialization to prevent undefined behavior
    memset(gN64_Reg_Base, 0, N64_RCP_SPACE_SIZE);
}

void HardwareRegs_Shutdown() {
    if (gN64_Reg_Base != nullptr) {
        if ((uintptr_t)gN64_Reg_Base == N64_K1_RCP_BASE_ADDR) {
            munmap(gN64_Reg_Base, N64_RCP_SPACE_SIZE);
        } else {
            aligned_free(gN64_Reg_Base);
        }
        gN64_Reg_Base = nullptr;
    }
}
