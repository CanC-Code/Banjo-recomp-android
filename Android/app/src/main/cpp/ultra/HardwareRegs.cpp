#include "HardwareRegs.h"
#include <cstdlib>
#include <cstring>

#define N64_REG_SPACE_SIZE 0x10000

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

void HardwareRegs_Init() {
    if (gN64_Reg_Base != nullptr) {
        return;
    }

    gN64_Reg_Base = (uint32_t*)aligned_malloc(16, N64_REG_SPACE_SIZE * sizeof(uint32_t));

    if (!gN64_Reg_Base) {
        // Hard fail — this should never happen
        abort();
    }

    memset(gN64_Reg_Base, 0, N64_REG_SPACE_SIZE * sizeof(uint32_t));
}

void HardwareRegs_Shutdown() {
    if (gN64_Reg_Base) {
        aligned_free(gN64_Reg_Base);
        gN64_Reg_Base = nullptr;
    }
}