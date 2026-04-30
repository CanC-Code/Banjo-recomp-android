#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

#include "n64_types.h"

extern "C" {
// Recompiled OS headers
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
#include <PR/os_vi.h>

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

/* ============================================================
   MISSING OS GLOBALS (Linker Fixes)
   These provide the symbols previously found in pirawdma.c, etc.
   ============================================================ */

OSPiHandle __osPiTable[2];             // For osCartRomInit
OSDevMgr   __osPiDevMgr;               // For osPiGetCmdQueue
OSViContext *__osViNext = nullptr;     // For osViBlack
OSViContext *__osViCurr = nullptr;     // For osViGetCurrentContext
int         __osViInit  = 0;           // For osCreateViManager

/* ============================================================
   MISSING OS FUNCTIONS (Linker Fixes)
   ============================================================ */

/**
 * The game calls this to start the PI Manager. Since we handle
 * DMA via HLE, we just log and return 0.
 */
s32 osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    LOGI("osCreatePiManager: HLE bridge active");
    return 0;
}

/**
 * Redirect Raw EPi DMA to our HLE Raw DMA function
 */
extern s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size);
s32 osEPiRawStartDma(OSPiHandle *handle, s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

/**
 * Internal VI init stub
 */
void __osViInit(void) {
    LOGI("__osViInit: HLE bridge active");
}

/* ============================================================
   Engine Entry & Main Loop
   ============================================================ */

AndroidBridgeGlobals* gBridgeGlobals = nullptr;

// Forward declarations for game subsystems
extern void core1_reset(void);
extern void core1_stepCPU(void);
extern void core2_stepFrame(void);

void initInterruptTables(void) {
    // Implementation is in exceptasm.cpp
}

void mainLoop(void) {
    LOGI("mainLoop: starting game loop");

    // Initialize the game's internal OS structures
    core1_reset();

    static const uint32_t TARGET_FRAME_US = 33333u; // 30 fps
    uint32_t frameCount = 0;

    while (true) {
        struct timespec ts_start, ts_end;
        clock_gettime(CLOCK_MONOTONIC, &ts_start);

        // --- Simulate one N64 frame ---
        core1_stepCPU();    
        core2_stepFrame();  

        if (gBridgeGlobals != nullptr) {
            gBridgeGlobals->frameCount++;
        }

        // --- Pacing ---
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

/* ============================================================
   Legacy & Misc Stubs
   ============================================================ */

void core1_loadOTR(uint8_t* data, size_t size) {
    LOGI("core1_loadOTR: %zu bytes (HLE bridge active)", size);
}

int func_80258A4C(void) { return 0; }
void func_8025A123(void) {}

} // extern "C"
