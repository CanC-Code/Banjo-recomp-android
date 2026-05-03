#include <jni.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <android/log.h>
#include <stdio.h>
#include <vector>
#include <string>
#include "rare_decompression.h"

#define LOG_TAG "BKA-Builder"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// Rareware FID Table Offset for Banjo-Kazooie (US 1.0)
#define ROM_FID_TABLE_OFFSET 0x5C30

// --- Manifest Structure (Matches Python struct.pack('<II32s8s')) ---
#pragma pack(push, 1)
struct ManifestEntry {
    uint32_t offset;
    uint32_t size;
    char name[32];
    char type[8];
};
#pragma pack(pop)

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

// Recursively create directories
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
JNIEXPORT void JNICALL Java_com_bkawrapper_OtrService_runNativeOtrGeneration(
    JNIEnv* env, jobject instance, jobject callbackObj, jint romFd, 
    jstring outDirPathStr, jstring manifestPathStr) {

    const char* outDirPath = env->GetStringUTFChars(outDirPathStr, NULL);
    const char* manifestPath = env->GetStringUTFChars(manifestPathStr, NULL);
    jclass callbackClass = env->GetObjectClass(callbackObj);
    jmethodID progressMid = env->GetMethodID(callbackClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    LOGI(">>> Named OTR Extraction Started (romFd: %d)", romFd);

    // 1. Load the Binary Manifest
    std::vector<ManifestEntry> manifest;
    int mFd = safe_open(manifestPath, O_RDONLY, 0);
    if (mFd != -1) {
        uint32_t mCount = 0;
        if (read(mFd, &mCount, 4) == 4) {
            manifest.resize(mCount);
            read(mFd, manifest.data(), mCount * sizeof(ManifestEntry));
        }
        safe_close(mFd);
        LOGI("Loaded %zu entries from manifest: %s", manifest.size(), manifestPath);
    } else {
        LOGE("Failed to open manifest at %s. Falling back to ID-based naming.", manifestPath);
    }

    // 2. Read the FID Entry Count from the ROM
    uint32_t entryCount = 0;
    if (safe_pread(romFd, &entryCount, 4, ROM_FID_TABLE_OFFSET) != 4) {
        LOGE("Failed to read ROM FID table offset");
        return;
    }
    entryCount = __builtin_bswap32(entryCount);
    LOGI("Detected %u file entries in ROM FID table", entryCount);

    if (entryCount == 0 || entryCount > 15000) {
        LOGE("Invalid entry count (%u). Aborting.", entryCount);
        return;
    }

    // 3. Extraction Loop
    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) return;

        uint32_t currentFileOffset = 0;
        uint32_t nextFileOffset = 0;

        safe_pread(romFd, &currentFileOffset, 4, ROM_FID_TABLE_OFFSET + 4 + (i * 4));
        safe_pread(romFd, &nextFileOffset, 4, ROM_FID_TABLE_OFFSET + 4 + ((i + 1) * 4));

        currentFileOffset = __builtin_bswap32(currentFileOffset);
        nextFileOffset = __builtin_bswap32(nextFileOffset);

        uint32_t fileSize = (nextFileOffset > currentFileOffset) ? (nextFileOffset - currentFileOffset) : 0;

        // Resolve Filename from Manifest or Fallback to Hex
        char fileName[256];
        if (i < manifest.size()) {
            // Remove trailing nulls/spaces from the 32-char fixed buffer
            snprintf(fileName, sizeof(fileName), "%s", manifest[i].name);
        } else {
            snprintf(fileName, sizeof(fileName), "unknown/%04X.bin", i);
        }

        int percentage = (int)(((i + 1) * 100) / entryCount);

        if (fileSize == 0 || fileSize > 0x1000000) {
            jstring jNameSkip = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jNameSkip);
            env->PopLocalFrame(NULL);
            continue;
        }

        char fullPath[512];
        snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        ensure_directories(fullPath);

        uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
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
                if (finalBuffer) free(finalBuffer);
            }
            free(compressedBuffer);
        }

        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        env->PopLocalFrame(NULL);
    }

    LOGI("OTR Generation Finished.");
    jstring doneMsg = env->NewStringUTF("Extraction Complete! Booting Game...");
    env->CallVoidMethod(callbackObj, progressMid, 100, doneMsg);

    env->ReleaseStringUTFChars(outDirPathStr, outDirPath);
    env->ReleaseStringUTFChars(manifestPathStr, manifestPath);
}
}
