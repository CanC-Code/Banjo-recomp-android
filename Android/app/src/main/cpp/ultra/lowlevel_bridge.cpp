#include <android/log.h>
#include <cstring>

extern "C" {
#include <PR/os_pi.h>
}

#define LOG_TAG "BKA_LOWLEVEL"
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

/* =========================
   PI Access (REAL SIGNATURES)
========================= */

extern "C" {

s32 osPiReadIo(u32 addr, u32* data) {
    if (data) *data = 0;
    return 0;
}

s32 osPiWriteIo(u32 addr, u32 value) {
    return 0;
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
   Unknown Core Functions
========================= */

int func_8025A6EC(...) {
    LOGW("func_8025A6EC stub");
    return 0;
}

int func_8025B1C0(...) {
    LOGW("func_8025B1C0 stub");
    return 0;
}

void func_8025C3F0(...) {
    LOGW("func_8025C3F0 stub");
}

}