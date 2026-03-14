#include <android/log.h>
#include <stdint.h>
#include <stddef.h>

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)

extern "C" {

// Fix for missing symbol in audio_helper/NativeBridge
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
