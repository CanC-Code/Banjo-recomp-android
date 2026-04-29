#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

extern "C" {
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
#include <PR/libaudio.h> // Fixed: Include this for the correct ALGlobals typedef
}

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/* =========================
   Globals
========================= */

// Fixed: Removed 'struct ALGlobals;' forward declaration.
// This now uses the correct definition from libaudio.h.
ALGlobals* alGlobals = nullptr;


/* =========================
   Engine Entry
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
   Audio
========================= */

void n_audioStep() {}


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
   Removed: Memory & PI & OS
   -------------------------
   Removing n64_memcpy, n64_memset, osPiReadIo, osPiWriteIo, 
   and all os... threading/timing/messaging stubs.
   Reason: These are now provided by libultrarecomp and the bridge files.
   Keeping them here would cause "Duplicate Symbol" linker errors.
========================= */


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
