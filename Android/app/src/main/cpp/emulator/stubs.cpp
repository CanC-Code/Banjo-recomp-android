#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// IMPORTANT: Include our bridge types to get AndroidBridgeGlobals
#include "n64_types.h"

extern "C" {
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
}

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/* =========================
   Globals
========================= */

/**
 * FIXED: Renamed to gBridgeGlobals with type AndroidBridgeGlobals.
 * This prevents the collision with the N64 SDK's internal 'ALGlobals' 
 * while giving us a safe place to store the Android screenBuffer.
 */
AndroidBridgeGlobals* gBridgeGlobals = nullptr;


/* =========================
   Engine Entry
========================= */

void initInterruptTables(void) {
    LOGI("initInterruptTables stub");
}

void mainLoop(void) {
    LOGW("mainLoop stub");
}


/* =========================
   Core Runtime
========================= */

void core1_reset(void) {
    LOGI("core1_reset");
}

void core1_stepCPU(void) {}
void core2_stepFrame(void) {}


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

int stub_return_0(void) { return 0; }
float stub_return_0f(void) { return 0.0f; }
void stub_void(void) {}


/* =========================
   Game-Specific Stubs
========================= */

int func_80258A4C(void) {
    LOGW("func_80258A4C stub");
    return 0;
}

void func_8025A123(void) {
    LOGW("func_8025A123 stub");
}

} // extern "C"
