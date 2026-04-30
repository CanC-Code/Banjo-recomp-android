#include "HardwareRegs.h"
#include <sys/mman.h>
#include <errno.h>
#include <android/log.h>
#include <cstdlib>
#include <cstring>

#define LOG_TAG "BKA_MEM"

// --- RCP Register Space ---
#define N64_K1_RCP_BASE_ADDR 0xA4000000 
#define N64_RCP_SPACE_SIZE 0x01000000 // 16MB

// --- PIF ROM/RAM Space ---
#define N64_K1_PIF_BASE_ADDR 0xBFC00000
#define N64_PIF_SPACE_SIZE 0x1000 // 4KB (Covers 0x1FC00000 to 0x1FC00FFF)

uint32_t* gN64_Reg_Base = nullptr;
uint32_t* gN64_PIF_Base = nullptr;

static void* aligned_malloc(size_t alignment, size_t size) {
    void* ptr = nullptr;
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

    // ==========================================
    // 1. RCP Registration Space Initialization
    // ==========================================
    void* target_rcp_addr = (void*)N64_K1_RCP_BASE_ADDR;
    gN64_Reg_Base = (uint32_t*)mmap(
        target_rcp_addr, N64_RCP_SPACE_SIZE, 
        PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0
    );

    if (gN64_Reg_Base == MAP_FAILED) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, 
            "MAP_FIXED failed for RCP at %p: %s. Switching to fallback.", target_rcp_addr, strerror(errno));
        
        gN64_Reg_Base = (uint32_t*)aligned_malloc(16, N64_RCP_SPACE_SIZE);
        if (gN64_Reg_Base == nullptr) {
            __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Critical memory allocation failure for RCP.");
            abort();
        }
    } else {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Successfully mapped RCP space at fixed address %p", gN64_Reg_Base);
    }
    memset(gN64_Reg_Base, 0, N64_RCP_SPACE_SIZE);

    // ==========================================
    // 2. PIF ROM/RAM Space Initialization
    // ==========================================
    void* target_pif_addr = (void*)N64_K1_PIF_BASE_ADDR;
    gN64_PIF_Base = (uint32_t*)mmap(
        target_pif_addr, N64_PIF_SPACE_SIZE, 
        PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0
    );

    if (gN64_PIF_Base == MAP_FAILED) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, 
            "MAP_FIXED failed for PIF at %p: %s. Switching to fallback.", target_pif_addr, strerror(errno));
        
        gN64_PIF_Base = (uint32_t*)aligned_malloc(16, N64_PIF_SPACE_SIZE);
        if (gN64_PIF_Base == nullptr) {
            __android_log_print(ANDROID_LOG_FATAL, LOG_TAG, "Critical memory allocation failure for PIF.");
            abort();
        }
    } else {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Successfully mapped PIF space at fixed address %p", gN64_PIF_Base);
    }
    memset(gN64_PIF_Base, 0, N64_PIF_SPACE_SIZE);
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
    
    if (gN64_PIF_Base != nullptr) {
        if ((uintptr_t)gN64_PIF_Base == N64_K1_PIF_BASE_ADDR) {
            munmap(gN64_PIF_Base, N64_PIF_SPACE_SIZE);
        } else {
            aligned_free(gN64_PIF_Base);
        }
        gN64_PIF_Base = nullptr;
    }
}
