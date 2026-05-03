#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <android/log.h>
#include <stdio.h>
#include "rare_decompression.h"

#define LOG_TAG "BKA-Builder"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// Rareware FID Table Offset for Banjo-Kazooie (US 1.0)
#define ROM_FID_TABLE_OFFSET 0x5C30

// --- Shadow-Proof Kernel System Calls ---
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

// External callback to NativeBridge
extern "C" void BKA_UpdateProgress(int percent, const char* status);

// Reads a 32-bit integer directly from the ROM and handles N64 Big Endian conversion
static uint32_t read_u32_rom(int fd, off_t offset) {
    uint32_t val = 0;
    if (safe_pread(fd, &val, 4, offset) == 4) {
        return __builtin_bswap32(val);
    }
    return 0;
}

void ensure_directories(const char* path) {
    char tmp[512];
    int i = 0;
    while(path[i] != '\0' && i < 511) { tmp[i] = path[i]; i++; }
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
bool OtrBuilder_run(int romFd, const char* outDirPath) {
    LOGI(">>> Self-Building OTR Extraction Started (romFd: %d)", romFd);
    BKA_UpdateProgress(0, "Scanning ROM Structure...");

    // 1. Read the number of entries from the ROM's internal FID table
    uint32_t entryCount = read_u32_rom(romFd, ROM_FID_TABLE_OFFSET);
    LOGI("Detected %u file entries in ROM FID table", entryCount);

    if (entryCount == 0 || entryCount > 15000) {
        LOGE("FATAL: Invalid entry count %u in ROM. Is this a valid Banjo-Kazooie US 1.0 ROM?", entryCount);
        return false;
    }

    BKA_UpdateProgress(0, "Extracting Assets...");

    // 2. Loop through the internal ROM table
    for (uint32_t i = 0; i < entryCount; i++) {
        uint32_t currentFileOffset = read_u32_rom(romFd, ROM_FID_TABLE_OFFSET + 4 + (i * 4));
        uint32_t nextFileOffset    = read_u32_rom(romFd, ROM_FID_TABLE_OFFSET + 4 + ((i + 1) * 4));
        
        if (nextFileOffset < currentFileOffset) continue; // Protection against corrupted tables
        
        uint32_t fileSize = nextFileOffset - currentFileOffset;
        
        if (fileSize == 0 || fileSize > 0x1000000) continue; 

        char fileName[32];
        snprintf(fileName, sizeof(fileName), "%04X.bin", i);

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)::malloc(fileSize);
        if (compressedBuffer) {
            if (safe_pread(romFd, compressedBuffer, fileSize, currentFileOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;
                
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);

                uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : compressedBuffer;
                uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    safe_write(outFd, writePtr, writeSize);
                    safe_close(outFd);
                }
                if (finalBuffer) ::free(finalBuffer);
            }
            ::free(compressedBuffer);
        }

        // Update progress UI periodically
        if (i % 100 == 0 || i == entryCount - 1) {
            int percentage = (int)(((i + 1) * 100) / entryCount);
            BKA_UpdateProgress(percentage, fileName);
        }
    }

    LOGI(">>> Internal ROM Extraction Successfully Finished");
    BKA_UpdateProgress(100, "Extraction Complete! Booting Game...");
    return true;
}
}
