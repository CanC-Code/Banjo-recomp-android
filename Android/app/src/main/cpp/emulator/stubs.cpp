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
// Note: We avoid including PR/os_vi.h if it causes conflicts with our stubs
}

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

extern "C" {

/* ============================================================
   FIX 1: __osPiTable Type Mismatch
   The header expects a pointer, so we provide a pool and point to it.
   ============================================================ */
static OSPiHandle  sPiTablePool[2];
OSPiHandle* __osPiTable = sPiTablePool;

/* ============================================================
   FIX 2: OSViContext and VI Globals
   The compiler didn't recognize 'OSViContext', so we'll treat 
   it as a void pointer for the stubs.
   ============================================================ */
void* __osViNext = nullptr; 
void* __osViCurr = nullptr;

/* ============================================================
   FIX 3: osCreatePiManager Return Type
   The header defines this as 'void', but our stub used 's32'.
   ============================================================ */
void osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    LOGI("osCreatePiManager: HLE bridge active");
}

/* ============================================================
   FIX 4: __osViInit Name Conflict
   Removed the 'int' variable to prevent conflict with the function name.
   ============================================================ */
void __osViInit(void) {
    LOGI("__osViInit: HLE bridge active");
}

/* ============================================================
   FIX 5: osEPiRawStartDma 
   Redirecting to our HLE DMA implementation.
   ============================================================ */
extern s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size);
s32 osEPiRawStartDma(OSPiHandle *handle, s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

// Global for the PI device manager
OSDevMgr __osPiDevMgr;

/* ============================================================
   Engine Entry & Main Loop
   ============================================================ */

AndroidBridgeGlobals* gBridgeGlobals = nullptr;

extern void core1_reset(void);
extern void core1_stepCPU(void);
extern void core2_stepFrame(void);

void mainLoop(void) {
    LOGI("mainLoop: starting game loop");

    core1_reset();

    static const uint32_t TARGET_FRAME_US = 33333u; // 30 fps
    uint32_t frameCount = 0;

    while (true) {
        struct timespec ts_start, ts_end;
        clock_gettime(CLOCK_MONOTONIC, &ts_start);

        core1_stepCPU();    
        core2_stepFrame();  

        if (gBridgeGlobals != nullptr) {
            gBridgeGlobals->frameCount++;
        }

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
   Generic Fallbacks
========================= */
void core1_loadOTR(uint8_t* data, size_t size) {
    LOGI("core1_loadOTR: legacy path ignored");
}

int func_80258A4C(void) { return 0; }
void func_8025A123(void) {}
void initInterruptTables(void) {}

} // extern "C"
