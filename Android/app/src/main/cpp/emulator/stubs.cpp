#include <android/log.h>
#include <stdint.h>
#include <stddef.h>

// Note: ALGlobals and other N64 types are provided by n64_types.h, 
// which is force-included via your CMakeLists.txt.

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

/**
 * Game Engine Symbols
 * These resolve "undefined symbol" errors during linking.
 */

// Define the pointer using the exact type declared in the SDK (libaudio.h)
ALGlobals* alGlobals = nullptr; 

// Engine entry points required by NativeBridge.cpp
void initInterruptTables() {
    LOGI("initInterruptTables: Stubbed");
}

void mainLoop() {
    // Stubbed: Prevents an infinite loop during verification builds
}

/**
 * Audio and OTR System Stubs
 */

void n_audioStep() {
    // Placeholder for audio processing
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
