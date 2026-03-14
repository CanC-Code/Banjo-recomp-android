#include "otr_builder.h"
#include "rare_decompression.h"
#include <android/log.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>

#define LOG_TAG "OtrBuilder"

void ensure_directories(const char* path) {
    char tmp[512];
    char* p = NULL;
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = 0;
            mkdir(tmp, S_IRWXU);
            *p = '/';
        }
    }
}

extern "C" {
static JavaVM* g_vm = nullptr;
void otr_builder_set_jvm(JavaVM* vm) { g_vm = vm; }

void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                           int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                           const char* outDirPath) {

    // 1. Read the Entry Count from the first 4 bytes (Little Endian)
    uint32_t entryCount = *(uint32_t*)manifestPtr;
    
    // 2. The records start AFTER the 4-byte header
    uint8_t* recordStart = manifestPtr + 4;

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Manifest loaded. Entries: %u", entryCount);

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(10) < 0) return;

        // Each record is 48 bytes
        uint8_t* record = recordStart + (i * 48);
        
        // Offset and Size are Little Endian (as per struct.pack '<II...')
        uint32_t romOffset = *(uint32_t*)(record + 0);
        uint32_t fileSize  = *(uint32_t*)(record + 4);
        
        // Name is 32 bytes
        char fileName[33];
        memcpy(fileName, record + 8, 32);
        fileName[32] = '\0';

        // Filter out records with 0 size (like the last entry in your script)
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
                
                // Check for Rare Magic 0x1172 inside decompress_rare_asset
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

        // Update Progress
        int percentage = (int)((i * 100) / entryCount);
        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        
        env->PopLocalFrame(NULL);
    }

    jstring doneMsg = env->NewStringUTF("Extraction Complete");
    env->CallVoidMethod(callbackObj, progressMid, 100, doneMsg);
}
}
