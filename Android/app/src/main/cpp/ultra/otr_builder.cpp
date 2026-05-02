// app/src/main/cpp/otr_builder.cpp

#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include "rare_decompression.h"

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

// --- 2. Progress Callback Helper ---
// Sourced from NativeBridge.cpp to safely handle JNI threading natively
extern "C" void BKA_UpdateProgress(int percent, const char* status);

// --- 3. Shadow-Proof Memory & Strings ---
static uint32_t read_u32_safe(const uint8_t* ptr) {
    uint32_t val;
    uint8_t* dst = (uint8_t*)&val;
    for(int i = 0; i < 4; i++) dst[i] = ptr[i];
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
void OtrBuilder_run(int romFd, AAssetManager* assetMgr, const char* outDirPath) {
    BKA_UpdateProgress(0, "DEBUG 1: Entered native extraction");

    AAsset* manifestAsset = AAssetManager_open(assetMgr, "manifest.bin", AASSET_MODE_BUFFER);
    if (!manifestAsset) {
        BKA_UpdateProgress(0, "ERROR: manifest.bin not found in assets");
        return;
    }

    const uint8_t* manifestPtr = (const uint8_t*)AAsset_getBuffer(manifestAsset);
    off_t manifestSize = AAsset_getLength(manifestAsset);

    if (!manifestPtr || manifestSize < 4) {
        BKA_UpdateProgress(0, "ERROR: Manifest is empty or invalid");
        AAsset_close(manifestAsset);
        return;
    }

    BKA_UpdateProgress(0, "DEBUG 2: Reading manifest header");
    uint32_t entryCount = read_u32_safe(manifestPtr);
    const uint8_t* recordStart = manifestPtr + 4;

    if (entryCount == 0 || entryCount > 50000) {
        BKA_UpdateProgress(0, "ERROR: Invalid entry count");
        AAsset_close(manifestAsset);
        return;
    }

    BKA_UpdateProgress(0, "DEBUG 3: Entering extraction loop");

    for (uint32_t i = 0; i < entryCount; i++) {
        const uint8_t* record = recordStart + (i * 48);
        if (record + 48 > manifestPtr + manifestSize) {
            break;
        }

        uint32_t romOffset = read_u32_safe(record + 0);
        uint32_t fileSize  = read_u32_safe(record + 4);

        char fileName[33];
        for(int j = 0; j < 32; j++) fileName[j] = *(record + 8 + j);
        fileName[32] = '\0';

        int percentage = (int)(((i + 1) * 100) / entryCount);

        if (fileSize == 0) {
            BKA_UpdateProgress(percentage, fileName);
            continue;
        }

        if (i == 0) BKA_UpdateProgress(0, "DEBUG 4: Setting up file path");

        char fullPath[512];
        int pIdx = 0;
        while(outDirPath[pIdx] != '\0' && pIdx < 400) { fullPath[pIdx] = outDirPath[pIdx]; pIdx++; }
        fullPath[pIdx++] = '/';
        int nIdx = 0;
        while(fileName[nIdx] != '\0' && pIdx < 510) { fullPath[pIdx++] = fileName[nIdx++]; }
        fullPath[pIdx] = '\0';

        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)::malloc(fileSize);
        if (compressedBuffer) {
            if (i == 0) BKA_UpdateProgress(0, "DEBUG 5: Reading ROM");

            if (safe_pread(romFd, compressedBuffer, fileSize, romOffset) == (ssize_t)fileSize) {
                uint32_t decompressedSize = 0;

                if (i == 0) BKA_UpdateProgress(0, "DEBUG 6: Decompressing asset");
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);

                uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : compressedBuffer;
                uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                if (i == 0) BKA_UpdateProgress(0, "DEBUG 7: Writing file to disk");
                int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    safe_write(outFd, writePtr, writeSize);
                    safe_close(outFd);
                }
                if (finalBuffer) ::free(finalBuffer);
            }
            ::free(compressedBuffer);
        }

        if (i == 0) BKA_UpdateProgress(0, "DEBUG 8: First file completely successful!");

        BKA_UpdateProgress(percentage, fileName);
    }

    AAsset_close(manifestAsset);
    BKA_UpdateProgress(100, "Extraction Complete! Booting Game...");
}
}
