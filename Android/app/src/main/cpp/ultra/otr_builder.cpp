#include <jni.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <android/log.h>
#include "rare_decompression.h"

#define LOG_TAG "OtrBuilder"

// Helper to prevent Alignment Faults on ARM64
static uint32_t read_u32_safe(uint8_t* ptr) {
    uint32_t val;
    memcpy(&val, ptr, 4);
    return val;
}

extern "C" {

void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                           int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                           const char* outDirPath) {
    if (!manifestPtr || manifestSize < 4) return;

    uint32_t entryCount = read_u32_safe(manifestPtr);
    uint8_t* recordStart = manifestPtr + 4;

    for (uint32_t i = 0; i < entryCount; i++) {
        uint8_t* record = recordStart + (i * 48);

        // Safe extraction of binary data
        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);

        char fileName[33];
        memcpy(fileName, record + 8, 32);
        fileName[32] = '\0';

        if (fileSize == 0) continue;

        // Perform the read/decompress/write cycle
        uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
        if (compressedBuffer) {
            if (pread(romFd, compressedBuffer, fileSize, romOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);

                // Write the file to the app's internal storage
                char fullPath[512];
                snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
                
                // (Note: ensure_directories logic remains here)
                int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    write(outFd, (finalBuffer ? finalBuffer : compressedBuffer), 
                          (finalBuffer ? decompressedSize : fileSize));
                    close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
            }
            free(compressedBuffer);
        }

        // Notify Java UI of progress
        if (callbackObj && progressMid && (i % 5 == 0)) {
            int percentage = (int)((i * 100) / entryCount);
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
            env->DeleteLocalRef(jName);
        }
    }
}
}
