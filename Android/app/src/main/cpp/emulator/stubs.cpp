#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

extern "C" {
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
#include <PR/libaudio.h> // Include this to get the correct ALGlobals definition
}

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/* =========================
   Globals
========================= */

// Now using the definition provided by libaudio.h
ALGlobals* alGlobals = nullptr;


/* =========================
   Engine / Bridge Stubs
========================= */

void initInterruptTables() {
    LOGI("initInterruptTables stub");
}

void mainLoop() {
    LOGW("mainLoop stub");
}


/* =========================
   Core Runtime
========================= */

void core1_reset() {
    LOGI("core1_reset");
}

void core1_stepCPU() {}
void core2_stepFrame() {}


/* =========================
   OTR / Assets
========================= */

void core1_loadOTR(uint8_t* data, size_t size) {
    if (!data || size == 0) {
        LOGW("core1_loadOTR invalid");
        return;
    }
    LOGI("Loaded OTR (%zu bytes)", size);
}

/* =========================
   Generic Fallbacks
========================= */

int stub_return_0() { return 0; }
float stub_return_0f() { return 0.0f; }
void stub_void() {}


/* =========================
   Game-Specific Stubs
========================= */

int func_80258A4C(...) {
    LOGW("func_80258A4C stub");
    return 0;
}

void func_8025A123(...) {
    LOGW("func_8025A123 stub");
}

} // extern "C"
