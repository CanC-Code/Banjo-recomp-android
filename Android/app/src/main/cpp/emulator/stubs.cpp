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
   1. OS GLOBALS & LINKER FIXES
   ============================================================ */

static OSPiHandle sPiTablePool[2];
OSPiHandle* __osPiTable = sPiTablePool;

void* __osViNext = nullptr; 
void* __osViCurr = nullptr;
OSDevMgr __osPiDevMgr;

void osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    LOGI("BKA-HLE: osCreatePiManager initialized.");
}

void __osViInit(void) {
    LOGI("BKA-HLE: __osViInit executed.");
}

/* ============================================================
   2. HLE MESSAGE QUEUE (Anti-Deadlock)
   These replace the blocking N64 OS calls.
   ============================================================ */

s32 osRecvMesg(OSMesgQueue *mq, OSMesg *msg, s32 flag) {
    // We return 0 to indicate a message was "received". 
    // This prevents the engine from hanging on osRecvMesg(..., OS_MESG_BLOCK).
    if (msg != NULL) {
        *msg = (OSMesg)0xDEADC0DE; 
    }
    return 0; 
}

s32 osSendMesg(OSMesgQueue *mq, OSMesg msg, s32 flag) {
    return 0; 
}

s32 osJamMesg(OSMesgQueue *mq, OSMesg msg, s32 flag) {
    return 0; 
}

/* ============================================================
   3. HLE DMA REDIRECTION
   ============================================================ */

extern s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size);
s32 osEPiRawStartDma(OSPiHandle *handle, s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

/* ============================================================
   4. GAME ENTRY POINTS & ENGINE DRIVER
   ============================================================ */

extern void func_80000450(int32_t arg0); 
AndroidBridgeGlobals* gBridgeGlobals = nullptr;

void core1_reset(void) {
    LOGI("BKA-CORE: System Reset.");
}

void core1_stepCPU(void) {
    static bool engine_ignited = false;
    if (!engine_ignited) {
        LOGI("BKA-STUBS: >>> IGNITING ENGINE (func_80000450) <<<");
        engine_ignited = true;
        func_80000450(0); 
    }
}

void mainLoop(void) {
    LOGI("BKA-STUBS: mainLoop starting.");
    core1_reset();

    static const uint32_t TARGET_FRAME_US = 33333u; 
    uint32_t frameCount = 0;

    while (true) {
        struct timespec ts_start, ts_end;
        clock_gettime(CLOCK_MONOTONIC, &ts_start);

        core1_stepCPU();    

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
            LOGI("BKA-STUBS: %u frames processed", frameCount);
        }
    }
}

/* ============================================================
   5. MISC FALLBACKS
   ============================================================ */

void core1_loadOTR(uint8_t* data, size_t size) {}
int  func_80258A4C(void) { return 0; }
void func_8025A123(void) {}
void initInterruptTables(void) {}

} // extern "C"
