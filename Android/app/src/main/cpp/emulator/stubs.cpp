#include <android/log.h>
#include <stdint.h>
#include <stddef.h>

// Note: n64_types.h is automatically included via CMake, 
// providing the real definition of ALGlobals.

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

/**
 * Global Variable Definitions
 * These resolve "undefined symbol" errors during linking.
 */

// The type 'ALGlobals' is defined in the SDK's libaudio.h.
// We just need to define the actual pointer variable here.
void* alGlobals = nullptr; 

// Engine entry points required by NativeBridge.cpp
void initInterruptTables() {
    LOGI("initInterruptTables: Stubbed");
}

void mainLoop() {
    // Stubbed: Prevents the app from entering an empty infinite loop
}

/**
 * Audio and OTR System Stubs
 */

void n_audioStep() {
    // Native audio processing placeholder
}

void core1_loadOTR(uint8_t* data, size_t size) {
    if (!data) return;
    LOGI("core1_loadOTR: Loading OTR data (Size: %zu bytes)", size);
}

void core1_reset() {
    LOGI("core1_reset called");
}

void core1_stepCPU() {}
void core2_stepFrame() {}

} // extern "C"
