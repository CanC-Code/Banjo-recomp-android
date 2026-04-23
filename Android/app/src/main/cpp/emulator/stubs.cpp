#include <android/log.h>
#include <stdint.h>
#include <stddef.h>

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

/**
 * Game Engine Symbols
 * These are required by NativeBridge.cpp but are located in the /src folder
 * which we are currently excluding from the build.
 */

// Dummy type for the Audio Global structure
typedef struct { uint8_t dummy; } ALGlobals;
ALGlobals* alGlobals = nullptr;

// Engine initialization called during nativeGameBoot
void initInterruptTables() {
    LOGI("initInterruptTables: Stubbed");
}

// The main loop that drives the recompiled game logic
void mainLoop() {
    // Stubbed to prevent the app from hanging on a loop that does nothing
}

/**
 * Audio and OTR Logic
 * Placeholders for the bridge to communicate with the asset and audio systems.
 */

void n_audioStep() {
    // Stub: Native audio processing placeholder
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
