#include <jni.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <android/log.h>
#include "rare_decompression.h"

#define LOG_TAG "OtrBuilder"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// Helper to prevent ARM64 Alignment Crashes
static uint32_t read_u32_safe(uint8_t* ptr) {
    uint32_t val;
    memcpy(&val, ptr, 4);
    return val;
}

void ensure_directories(const char* path) {
    char tmp[512];
    char* p = NULL;
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (p = tmp + 1; *p; p++) {
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

    if (!manifestPtr || manifestSize < 4) {
        LOGE("run_native_otr: Manifest pointer is NULL or too small!");
        return;
    }

    // 1. Read the Entry Count from the first 4 bytes (Matching your old script!)
    uint32_t entryCount = read_u32_safe(manifestPtr);
    uint8_t* recordStart = manifestPtr + 4;

    LOGI("Manifest loaded. Entries: %u", entryCount);

    if (entryCount == 0 || entryCount > 50000) {
        LOGE("run_native_otr: Invalid entry count (%u). Aborting.", entryCount);
        return;
    }

    for (uint32_t i = 0; i < entryCount; i++) {
        // CRITICAL: Prevent JNI Local Reference Overflow on long loops
        if (env->PushLocalFrame(10) < 0) return;

        // Each record is 48 bytes
        uint8_t* record = recordStart + (i * 48);
        
        if (record + 48 > manifestPtr + manifestSize) {
            LOGE("Buffer overflow prevented at entry %u", i);
            env->PopLocalFrame(NULL);
            break;
        }

        // Offset and Size
        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);
        
        // Name is 32 bytes
        char fileName[33];
        memcpy(fileName, record + 8, 32);
        fileName[32] = '\0';

        if (fileSize == 0) {
            env->PopLocalFrame(NULL);
            continue;
        }

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
        if (compressedBuffer) {
            if (pread(romFd, compressedBuffer, fileSize, romOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;
                
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);
                
                uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : compressedBuffer;
                uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    write(outFd, writePtr, writeSize);
                    close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
            } else {
                LOGE("Failed to read ROM for %s", fileName);
            }
            free(compressedBuffer);
        }

        // Update Progress
        int percentage = (int)(((i + 1) * 100) / entryCount);
        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        
        // Clean up JNI references for this loop iteration
        env->PopLocalFrame(NULL);
    }

    LOGI("Extraction Complete!");
}
}
