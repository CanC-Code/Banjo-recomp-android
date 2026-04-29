#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <unistd.h>   // usleep
#include <time.h>     // clock_gettime, CLOCK_MONOTONIC — required explicitly on NDK aarch64-android26

// IMPORTANT: Include our bridge types to get AndroidBridgeGlobals
#include "n64_types.h"

extern "C" {
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
}

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

extern "C" {

/* =========================
   Globals
========================= */

/**
 * gBridgeGlobals – allocated and zeroed in NativeBridge::nativeGameBoot
 * before mainLoop() is called.
 */
AndroidBridgeGlobals* gBridgeGlobals = nullptr;

/* =========================
   Forward declarations for game subsystems
========================= */
extern void core1_reset(void);
extern void core1_stepCPU(void);
extern void core2_stepFrame(void);

/* =========================
   Engine Entry
========================= */

void initInterruptTables(void) {
    // Real implementation is in exceptasm.cpp.
    // This stub is kept as a safety fallback only; the linker will prefer
    // the definition in exceptasm.cpp due to link order in CMakeLists.
    LOGI("initInterruptTables: fallback stub (should not be reached)");
}

/**
 * mainLoop
 *
 * This is the game's top-level driver.  It is called from nativeGameBoot
 * on a dedicated background thread and must not return during normal play.
 *
 * Pacing: we target 30 fps (~33 333 us per frame).  The VI interrupt on
 * real N64 hardware fires at 60 Hz; Banjo runs its game logic at 30 Hz by
 * processing every other VI event.  We mirror that by sleeping the deficit
 * after each frame's work rather than busy-spinning.
 */
void mainLoop(void) {
    LOGI("mainLoop: starting game loop");

    // Reset game state to a known-good initial condition
    core1_reset();

    static const uint32_t TARGET_FRAME_US = 33333u; // 30 fps
    uint32_t frameCount = 0;

    while (true) {
        struct timespec ts_start, ts_end;
        clock_gettime(CLOCK_MONOTONIC, &ts_start);

        // --- Simulate one N64 frame ---
        core1_stepCPU();    // RSP / RCP microcode + game logic tick
        core2_stepFrame();  // Scene update, animation, camera

        // Update frame counter so GLRenderer can detect a new frame
        if (gBridgeGlobals != nullptr) {
            gBridgeGlobals->frameCount++;
        }

        // --- Pace to target frame rate ---
        clock_gettime(CLOCK_MONOTONIC, &ts_end);
        uint32_t elapsed_us = (uint32_t)(
            (uint64_t)(ts_end.tv_sec  - ts_start.tv_sec)  * 1000000u +
            (uint64_t)(ts_end.tv_nsec - ts_start.tv_nsec) / 1000u
        );

        if (elapsed_us < TARGET_FRAME_US) {
            usleep(TARGET_FRAME_US - elapsed_us);
        }

        if ((++frameCount % 300) == 0) {
            LOGI("mainLoop: %u frames rendered", frameCount);
        }
    }
}

/* =========================
   Core Runtime
========================= */

void core1_reset(void) {
    LOGI("core1_reset: subsystem reset");
}

void core1_stepCPU(void) {
    // Placeholder: the recompiled game C code drives itself.
    // When the recompiled translation units are linked in, they will
    // shadow these stubs via normal C linkage resolution.
}

void core2_stepFrame(void) {
    // Placeholder -- same as above.
}

/* =========================
   OTR / Assets
========================= */

/**
 * core1_loadOTR is kept for legacy call sites that may exist in the
 * recompiled source.  The real asset loading now goes through
 * ResourceMgr_HandleDma, which is triggered by osPiRawStartDma.
 */
void core1_loadOTR(uint8_t* data, size_t size) {
    if (!data || size == 0) {
        LOGW("core1_loadOTR: invalid arguments (ignored)");
        return;
    }
    LOGI("core1_loadOTR: %zu bytes (legacy path -- ResourceMgr handles DMA now)", size);
}

/* =========================
   Generic Fallbacks
========================= */

int   stub_return_0(void)  { return 0;    }
float stub_return_0f(void) { return 0.0f; }
void  stub_void(void)      {}

/* =========================
   Game-Specific Stubs
========================= */

int func_80258A4C(void) {
    return 0;
}

void func_8025A123(void) {
    // no-op stub
}

} // extern "C"
