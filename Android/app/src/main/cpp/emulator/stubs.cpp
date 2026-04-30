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

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

/* ============================================================
   1. OS GLOBALS (Linker Fixes)
   These satisfy the requirements of the recompiled game code
   after we filtered out the original hardware-specific .c files.
   ============================================================ */

// The header expects OSPiHandle*, so we provide memory and point to it.
static OSPiHandle sPiTablePool[2];
OSPiHandle* __osPiTable = sPiTablePool;

// Treat VI Contexts as void pointers to avoid "unknown type" errors.
void* __osViNext = nullptr; 
void* __osViCurr = nullptr;

// Global Peripheral Interface (PI) Manager status
OSDevMgr __osPiDevMgr;

/* ============================================================
   2. HLE OS FUNCTIONS
   These replace N64 hardware routines with safe Android stubs.
   ============================================================ */

/**
 * Match the header: extern void osCreatePiManager(...)
 */
void osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    LOGI("BKA-HLE: osCreatePiManager initialized.");
}

/**
 * Internal Video Interface initialization
 */
void __osViInit(void) {
    LOGI("BKA-HLE: __osViInit executed.");
}

/**
 * Redirect Extended PI DMA to our Android-compatible HLE DMA.
 */
extern s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size);
s32 osEPiRawStartDma(OSPiHandle *handle, s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

/* ============================================================
   3. GAME ENTRY POINTS & ENGINE DRIVER
   ============================================================ */

// The recompiled Entry Point found in bk_boot_1050.c
extern void func_80000450(int32_t arg0); 

// Global bridge pointer for screen buffers and frame counts
AndroidBridgeGlobals* gBridgeGlobals = nullptr;

// Subsystem forward declarations
void core1_reset(void) {
    LOGI("BKA-CORE: System Reset.");
}

/**
 * This function triggers the recompiled game logic.
 */
void core1_stepCPU(void) {
    static bool engine_ignited = false;
    
    if (!engine_ignited) {
        LOGI("BKA-STUBS: >>> IGNITING ENGINE (func_80000450) <<<");
        engine_ignited = true;
        
        // This is the "Big Bang" for the game logic.
        // arg 0 = 0 is the default N64 boot mode.
        func_80000450(0); 
    }
}

/**
 * mainLoop
 * Targeted at 30 FPS. This drives the whole app.
 */
void mainLoop(void) {
    LOGI("BKA-STUBS: mainLoop starting.");
    
    core1_reset();

    static const uint32_t TARGET_FRAME_US = 33333u; // ~30.0 fps
    uint32_t frameCount = 0;

    while (true) {
        struct timespec ts_start, ts_end;
        clock_gettime(CLOCK_MONOTONIC, &ts_start);

        // 1. Run the recompiled game logic
        core1_stepCPU();    
        
        // 2. Notify the Renderer that a frame has passed
        if (gBridgeGlobals != nullptr) {
            gBridgeGlobals->frameCount++;
        }

        // 3. Pace the loop
        clock_gettime(CLOCK_MONOTONIC, &ts_end);
        uint32_t elapsed_us = (uint32_t)(
            (uint64_t)(ts_end.tv_sec  - ts_start.tv_sec)  * 1000000u +
            (uint64_t)(ts_end.tv_nsec - ts_start.tv_nsec) / 1000u
        );

        if (elapsed_us < TARGET_FRAME_US) {
            usleep(TARGET_FRAME_US - elapsed_us);
        }

        // Log progress every 10 seconds (300 frames)
        if ((++frameCount % 300) == 0) {
            LOGI("BKA-STUBS: %u frames processed", frameCount);
        }
    }
}

/* ============================================================
   4. MISCELLANEOUS FALLBACKS
   Required to satisfy the linker for Rare-specific calls.
   ============================================================ */

void core1_loadOTR(uint8_t* data, size_t size) {}
int  func_80258A4C(void) { return 0; }
void func_8025A123(void) {}
void initInterruptTables(void) {}

} // extern "C"
