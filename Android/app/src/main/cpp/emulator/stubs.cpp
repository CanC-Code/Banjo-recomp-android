#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

extern "C" {
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
// Note: We don't include libaudio.h here because it is already 
// provided by the forced-include in CMake (n64_types.h).
}

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/* =========================
   Globals
========================= */

/**
 * FIXED: Matching the type declared in the forced-include headers.
 * This resolves the "redefinition with a different type" error.
 */
ALGlobals* alGlobals = nullptr;


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

// FIXED: Removed the bare '...' variadic arguments. 
// Using '(void)' or an empty signature is safer in an extern "C" block
// unless the exact C header declares a specific variadic signature.
int func_80258A4C(void) {
    LOGW("func_80258A4C stub");
    return 0;
}

void func_8025A123(void) {
    LOGW("func_8025A123 stub");
}

} // extern "C"
