#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/**
 * ============================
 * Core Engine Globals
 * ============================
 */

// Provided by libaudio.h via n64_types.h
ALGlobals* alGlobals = nullptr;


/**
 * ============================
 * Engine Entry Points
 * ============================
 */

void initInterruptTables() {
    LOGI("initInterruptTables: Stubbed");
}

void mainLoop() {
    // Prevent dead loop lockup
    LOGW("mainLoop called (stub) — skipping execution");
}


/**
 * ============================
 * Core Runtime Stubs
 * ============================
 */

void core1_reset() {
    LOGI("core1_reset called");
}

void core1_stepCPU() {
    // no-op
}

void core2_stepFrame() {
    // no-op
}


/**
 * ============================
 * Audio Stubs
 * ============================
 */

void n_audioStep() {
    // no-op
}


/**
 * ============================
 * Resource / OTR
 * ============================
 */

void core1_loadOTR(uint8_t* data, size_t size) {
    if (!data || size == 0) {
        LOGW("core1_loadOTR: invalid data");
        return;
    }

    LOGI("core1_loadOTR: Loaded OTR (%zu bytes)", size);
}


/**
 * ============================
 * Memory / Libultra Stubs
 * ============================
 */

void* n64_memcpy(void* dst, const void* src, size_t size) {
    return memcpy(dst, src, size);
}

void* n64_memset(void* dst, int val, size_t size) {
    return memset(dst, val, size);
}


/**
 * ============================
 * Low-Level IO Stubs
 * ============================
 */

int osPiReadIo(...) {
    LOGW("osPiReadIo called (stub)");
    return 0;
}

int osPiWriteIo(...) {
    LOGW("osPiWriteIo called (stub)");
    return 0;
}


/**
 * ============================
 * Safe Default Return Helpers
 * ============================
 */

int stub_return_0() {
    return 0;
}

float stub_return_0f() {
    return 0.0f;
}

void stub_void() {
    // no-op
}


/**
 * ============================
 * Example Missing Function Stubs
 * (ADD MORE FROM LINKER ERRORS)
 * ============================
 */

// These are placeholders — expand based on linker output

int func_80258A4C(...) {
    LOGW("func_80258A4C stub");
    return 0;
}

void func_8025A123(...) {
    LOGW("func_8025A123 stub");
}

} // extern "C"