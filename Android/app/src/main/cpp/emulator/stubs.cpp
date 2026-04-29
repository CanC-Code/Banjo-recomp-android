#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

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
   Memory
========================= */

void* n64_memcpy(void* dst, const void* src, size_t size) {
    return memcpy(dst, src, size);
}

void* n64_memset(void* dst, int val, size_t size) {
    return memset(dst, val, size);
}


/* =========================
   PI (FIXED SIGNATURES)
========================= */

s32 osPiReadIo(u32 addr, u32* data) {
    if (data) {
        *data = 0;
    }
    return 0;
}

s32 osPiWriteIo(u32 addr, u32 value) {
    return 0;
}


/* =========================
   Threading
========================= */

void osCreateThread(OSThread* t, OSId id, void (*entry)(void*), void* arg,
                    void* stack, OSPri pri) {
    LOGW("osCreateThread stub");
}

void osStartThread(OSThread* t) {
    LOGW("osStartThread stub");
}

OSPri osGetThreadPri(OSThread* t) {
    return 0;
}

void osSetThreadPri(OSThread* t, OSPri pri) {}


/* =========================
   Messaging
========================= */

void osCreateMesgQueue(OSMesgQueue* mq, OSMesg* buf, s32 count) {}

s32 osSendMesg(OSMesgQueue* mq, OSMesg msg, s32 flags) {
    return 0;
}

s32 osRecvMesg(OSMesgQueue* mq, OSMesg* msg, s32 flags) {
    if (msg) *msg = 0;
    return 0;
}


/* =========================
   Interrupts
========================= */

OSIntMask osSetIntMask(OSIntMask mask) {
    return 0;
}

void osYieldThread(void) {}


/* =========================
   Timing
========================= */

u64 osGetTime(void) {
    return 0;
}

u32 osGetCount(void) {
    return 0;
}


/* =========================
   Generic Fallbacks
========================= */

int stub_return_0() { return 0; }
float stub_return_0f() { return 0.0f; }
void stub_void() {}


/* =========================
   Example Game Stubs
========================= */

int func_80258A4C(...) {
    LOGW("func_80258A4C stub");
    return 0;
}

void func_8025A123(...) {
    LOGW("func_8025A123 stub");
}

} // extern "C"