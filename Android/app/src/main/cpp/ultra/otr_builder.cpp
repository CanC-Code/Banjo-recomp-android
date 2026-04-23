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
    
    if (!manifestPtr || manifestSize < 12) {
        LOGE("run_native_otr: Manifest is missing or too small!");
        return;
    }

    // 1. Read ManifestHeader (12 bytes total)
    uint32_t magic      = read_u32_safe(manifestPtr + 0);
    uint32_t entryCount = read_u32_safe(manifestPtr + 4);
    uint32_t version    = read_u32_safe(manifestPtr + 8);

    LOGI("Manifest Header -> Magic: 0x%X, Entries: %u, Version: %u", magic, entryCount, version);

    // Safety check - adjust 50000 if your game has more assets than that!
    if (entryCount == 0 || entryCount > 50000) { 
        LOGE("run_native_otr: Invalid entry count. Aborting.");
        return;
    }

    // 2. Start reading AssetEntry records (Starts after the 12-byte header)
    uint8_t* recordStart = manifestPtr + 12;

    for (uint32_t i = 0; i < entryCount; i++) {
        // Each AssetEntry is 144 bytes according to the header (4+4+4+4+128)
        uint8_t* record = recordStart + (i * 144);
        
        if (record + 144 > manifestPtr + manifestSize) {
            LOGE("Buffer overflow prevented at entry %u", i);
            break;
        }

        // 3. Extract the variables according to AssetEntry struct
        uint32_t romOffset  = read_u32_safe(record + 0);
        uint32_t compSize   = read_u32_safe(record + 4);
        uint32_t decompSize = read_u32_safe(record + 8);
        uint32_t type       = read_u32_safe(record + 12);

        char fileName[129];
        memcpy(fileName, record + 16, 128);
        fileName[128] = '\0'; // Guarantee null termination

        if (compSize == 0 || type == 0) continue; // Skip empty/skipped assets

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        ensure_directories(fullPath);

        // 4. File extraction and decompression
        uint8_t* compressedBuffer = (uint8_t*)malloc(compSize);
        if (compressedBuffer) {
            ssize_t bytesRead = pread(romFd, compressedBuffer, compSize, romOffset);
            if (bytesRead == (ssize_t)compSize) {
                
                uint8_t* finalBuffer = nullptr;
                uint32_t finalSize = compSize;

                // ASSET_TYPE_COMPRESSED = 1
                if (type == 1) {
                    uint32_t actualDecompSize = 0;
                    finalBuffer = decompress_rare_asset(compressedBuffer, compSize, &actualDecompSize);
                    if (finalBuffer) finalSize = actualDecompSize;
                }

                int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    write(outFd, (finalBuffer ? finalBuffer : compressedBuffer), finalSize);
                    close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
            } else {
                LOGE("Failed to read ROM for %s", fileName);
            }
            free(compressedBuffer);
        }

        // 5. Update Java UI
        int percentage = (int)(((i + 1) * 100) / entryCount);
        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        env->DeleteLocalRef(jName);
    }
    
    LOGI("run_native_otr: Extraction Complete!");
}
}
