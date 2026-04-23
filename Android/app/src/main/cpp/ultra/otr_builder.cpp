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
    
    if (!manifestPtr) {
        LOGE("run_native_otr: Manifest pointer is NULL!");
        return;
    }

    uint32_t entryCount = read_u32_safe(manifestPtr);
    LOGI("run_native_otr: Start! Entry Count detected: %u", entryCount);

    if (entryCount == 0 || entryCount > 50000) { // Safety check
        LOGE("run_native_otr: Invalid entry count!");
        return;
    }

    uint8_t* recordStart = manifestPtr + 4;

    for (uint32_t i = 0; i < entryCount; i++) {
        uint8_t* record = recordStart + (i * 48);
        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);

        char fileName[33];
        memcpy(fileName, record + 8, 32);
        fileName[32] = '\0';

        // Log the first 5 files specifically to confirm life
        if (i < 5) LOGI("Extracting [%u/%u]: %s (Offset: %u, Size: %u)", i+1, entryCount, fileName, romOffset, fileSize);

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
        if (compressedBuffer) {
            ssize_t bytesRead = pread(romFd, compressedBuffer, fileSize, romOffset);
            if (bytesRead == (ssize_t)fileSize) {
                uint32_t decompSize = 0;
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompSize);

                int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    write(outFd, (finalBuffer ? finalBuffer : compressedBuffer), 
                                 (finalBuffer ? decompSize : fileSize));
                    close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
            } else {
                LOGE("Failed to read ROM at offset %u. Expected %u, got %zd", romOffset, fileSize, bytesRead);
            }
            free(compressedBuffer);
        }

        // Update Java UI
        int percentage = (int)(((i + 1) * 100) / entryCount);
        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        env->DeleteLocalRef(jName);
    }
    LOGI("run_native_otr: All entries processed successfully.");
}
}
