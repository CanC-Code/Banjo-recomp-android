#include "otr_builder.h"
#include "rare_decompression.h"
#include <android/log.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>

#define LOG_TAG "OtrBuilder"

// Helper to safely read 32-bit values from potentially misaligned memory
uint32_t read_u32_safe(uint8_t* ptr) {
    uint32_t val;
    memcpy(&val, ptr, 4);
    return val;
}

extern "C" {

void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                           int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                           const char* outDirPath) {

    if (!manifestPtr || manifestSize < 4) return;

    // 1. Safe read of entry count
    uint32_t entryCount = read_u32_safe(manifestPtr);
    uint8_t* recordStart = manifestPtr + 4;

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Beginning OTR Generation. Entries: %u", entryCount);

    for (uint32_t i = 0; i < entryCount; i++) {
        uint8_t* record = recordStart + (i * 48);
        if (record + 48 > manifestPtr + manifestSize) break;

        // 2. Safe read of Offset and Size
        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);

        char fileName[33];
        memcpy(fileName, record + 8, 32);
        fileName[32] = '\0';

        if (fileSize == 0) continue;

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        
        // Ensure the subfolder exists (e.g., assets/text/...)
        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
        if (compressedBuffer) {
            // Read from ROM file descriptor passed from Java
            if (pread(romFd, compressedBuffer, fileSize, romOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;

                // Call our HLE decompression logic
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);

                uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : compressedBuffer;
                uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    write(outFd, writePtr, writeSize);
                    close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
            }
            free(compressedBuffer);
        }

        // Update UI Progress every 5 entries to reduce JNI overhead
        if (i % 5 == 0 || i == entryCount - 1) {
            int percentage = (int)((i * 100) / entryCount);
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
            env->DeleteLocalRef(jName); // Clean up JNI string to prevent ref overflow
        }
    }

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "OTR Generation Finished.");
}
}
