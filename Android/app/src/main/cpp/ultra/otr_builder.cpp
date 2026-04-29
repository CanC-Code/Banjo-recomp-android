#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include "rare_decompression.h"

// --- 1. Shadow-Proof Kernel System Calls ---
// These bypass the standard C library, making it impossible for the N64 game to shadow them.
static ssize_t safe_pread(int fd, void *buf, size_t count, off_t offset) {
    return syscall(SYS_pread64, fd, buf, count, offset);
}
static int safe_open(const char *pathname, int flags, mode_t mode) {
    return syscall(SYS_openat, AT_FDCWD, pathname, flags, mode);
}
static ssize_t safe_write(int fd, const void *buf, size_t count) {
    return syscall(SYS_write, fd, buf, count);
}
static int safe_close(int fd) {
    return syscall(SYS_close, fd);
}

// --- 2. Visual Debugger Helper ---
// Prints debug messages directly to your Android UI
void debug_ui(JNIEnv* env, jobject callbackObj, jmethodID progressMid, const char* msg) {
    if (!env || !callbackObj || !progressMid) return;
    jstring jMsg = env->NewStringUTF(msg);
    env->CallVoidMethod(callbackObj, progressMid, 0, jMsg);
    env->DeleteLocalRef(jMsg);
}

// --- 3. Shadow-Proof Memory & Strings ---
static uint32_t read_u32_safe(uint8_t* ptr) {
    uint32_t val;
    uint8_t* dst = (uint8_t*)&val;
    for(int i = 0; i < 4; i++) dst[i] = ptr[i]; // Manual copy bypasses N64 memcpy
    return val;
}

void ensure_directories(const char* path) {
    char tmp[512];
    int i = 0;
    while(path[i] != '\0' && i < 511) {
        tmp[i] = path[i];
        i++;
    }
    tmp[i] = '\0';
    
    for (char* p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = 0;
            mkdir(tmp, 0777);
            *p = '/';
        }
    }
}

extern "C" {
void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                           int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                           const char* outDirPath) {

    debug_ui(env, callbackObj, progressMid, "DEBUG 1: Entered native C++");

    if (!manifestPtr || manifestSize < 4) {
        debug_ui(env, callbackObj, progressMid, "ERROR: Manifest is NULL");
        return;
    }

    debug_ui(env, callbackObj, progressMid, "DEBUG 2: Reading manifest header");
    uint32_t entryCount = read_u32_safe(manifestPtr);
    uint8_t* recordStart = manifestPtr + 4;

    if (entryCount == 0 || entryCount > 50000) {
        debug_ui(env, callbackObj, progressMid, "ERROR: Invalid entry count");
        return;
    }

    debug_ui(env, callbackObj, progressMid, "DEBUG 3: Entering extraction loop");

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) return;

        uint8_t* record = recordStart + (i * 48);
        if (record + 48 > manifestPtr + manifestSize) {
            env->PopLocalFrame(NULL);
            break;
        }

        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);

        char fileName[33];
        for(int j = 0; j < 32; j++) fileName[j] = *(record + 8 + j);
        fileName[32] = '\0';

        int percentage = (int)(((i + 1) * 100) / entryCount);

        if (fileSize == 0) {
            jstring jNameSkip = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jNameSkip);
            env->PopLocalFrame(NULL);
            continue;
        }

        if (i == 0) debug_ui(env, callbackObj, progressMid, "DEBUG 4: Setting up file path");

        char fullPath[512];
        int pIdx = 0;
        while(outDirPath[pIdx] != '\0' && pIdx < 400) { fullPath[pIdx] = outDirPath[pIdx]; pIdx++; }
        fullPath[pIdx++] = '/';
        int nIdx = 0;
        while(fileName[nIdx] != '\0' && pIdx < 510) { fullPath[pIdx++] = fileName[nIdx++]; }
        fullPath[pIdx] = '\0';

        ensure_directories(fullPath);

        // :: scopes the compiler to the global standard library, ignoring N64 malloc
        uint8_t* compressedBuffer = (uint8_t*)::malloc(fileSize);
        if (compressedBuffer) {
            if (i == 0) debug_ui(env, callbackObj, progressMid, "DEBUG 5: Reading ROM");

            if (safe_pread(romFd, compressedBuffer, fileSize, romOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;

                if (i == 0) debug_ui(env, callbackObj, progressMid, "DEBUG 6: Decompressing asset");
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);

                uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : compressedBuffer;
                uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                if (i == 0) debug_ui(env, callbackObj, progressMid, "DEBUG 7: Writing file to disk");
                int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    safe_write(outFd, writePtr, writeSize);
                    safe_close(outFd);
                }
                if (finalBuffer) ::free(finalBuffer);
            }
            ::free(compressedBuffer);
        }

        if (i == 0) debug_ui(env, callbackObj, progressMid, "DEBUG 8: First file completely successful!");

        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);

        env->PopLocalFrame(NULL);
    }

    jstring doneMsg = env->NewStringUTF("Extraction Complete! Booting Game...");
    env->CallVoidMethod(callbackObj, progressMid, 100, doneMsg);
}
}
