#include <jni.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <android/log.h>
#include "rare_decompression.h"

#define LOG_TAG "BKA-Builder"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// --- 1. Shadow-Proof Kernel System Calls ---
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

// Helper to prevent ARM64 Alignment Crashes
static uint32_t read_u32_safe(const uint8_t* ptr) {
    uint32_t val;
    memcpy(&val, ptr, 4);
    return val;
}

// Recursively create directories for the outDirPath/fileName path
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

// External callback to NativeBridge
extern "C" void BKA_UpdateProgress(int percent, const char* status);

extern "C" {
bool OtrBuilder_run(int romFd, const uint8_t* manifestPtr, uint32_t manifestSize, const char* outDirPath) {
    LOGI(">>> OTR Extraction Started (romFd: %d)", romFd);

    if (!manifestPtr || manifestSize < 4) {
        LOGE("run_native_otr: Manifest pointer is NULL or too small!");
        return false;
    }

    // 1. Read the Entry Count (4-byte header)
    uint32_t entryCount = read_u32_safe(manifestPtr);
    const uint8_t* recordStart = manifestPtr + 4;

    LOGI("Manifest loaded. Entries to process: %u", entryCount);

    if (entryCount == 0 || entryCount > 50000) {
        LOGE("run_native_otr: Invalid entry count (%u). Aborting.", entryCount);
        return false;
    }

    for (uint32_t i = 0; i < entryCount; i++) {
        // Each record is 48 bytes based on the Python script (<II32s8s)
        const uint8_t* record = recordStart + (i * 48);
        
        if (record + 48 > manifestPtr + manifestSize) {
            LOGE("Buffer overflow prevented at entry %u", i);
            break;
        }

        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);
        
        char fileName[33];
        memcpy(fileName, record + 8, 32);
        fileName[32] = '\0';

        // Calculate percentage early so we can report progress even for skipped files
        int percentage = (int)(((i + 1) * 100) / entryCount);

        // Skip files with 0 size (like padding or tail markers) but still update the UI
        if (fileSize == 0) {
            BKA_UpdateProgress(percentage, fileName);
            continue;
        }

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
        if (compressedBuffer) {
            if (safe_pread(romFd, compressedBuffer, fileSize, romOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;
                
                // decompress_rare_asset handles the 0x1172 magic check
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);
                
                uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : compressedBuffer;
                uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    safe_write(outFd, writePtr, writeSize);
                    safe_close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
            } else {
                LOGE("Failed to read ROM for %s at offset %u", fileName, romOffset);
            }
            free(compressedBuffer);
        }

        // Periodic UI update to prevent swamping the Android message queue
        if (i % 50 == 0 || i == entryCount - 1) {
            BKA_UpdateProgress(percentage, fileName);
        }
    }

    // --- FINAL COMPLETION SIGNAL ---
    LOGI("OTR Generation Finished. Sending final 100%% signal.");
    BKA_UpdateProgress(100, "Extraction Complete! Booting Game...");
    return true;
}
}
