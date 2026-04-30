#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <android/log.h>

#define TAG "BKA-HardwareRegs"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

// -----------------------------------------------------------------------
// N64 Hardware Register Base (GLOBAL DEFINITION)
// -----------------------------------------------------------------------

extern "C" {
    uint32_t* gN64_Reg_Base = nullptr;
}

// Size: enough to cover full register space safely
// (you can tighten later if needed)
#define N64_REG_SPACE_SIZE (0x10000 / sizeof(uint32_t))

extern "C" void InitN64Registers() {
    if (gN64_Reg_Base != nullptr) {
        LOGI("gN64_Reg_Base already initialized");
        return;
    }

    gN64_Reg_Base = (uint32_t*)aligned_alloc(16, N64_REG_SPACE_SIZE * sizeof(uint32_t));

    if (!gN64_Reg_Base) {
        LOGE("Failed to allocate gN64_Reg_Base!");
        return;
    }

    memset(gN64_Reg_Base, 0, N64_REG_SPACE_SIZE * sizeof(uint32_t));

    LOGI("gN64_Reg_Base allocated at %p", gN64_Reg_Base);
}