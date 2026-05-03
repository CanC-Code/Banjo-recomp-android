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

#define ROM_FID_TABLE_OFFSET 0x5C30

enum RomFormat {
    FORMAT_Z64, // Big-Endian (Native N64)
    FORMAT_N64, // Little-Endian
    FORMAT_V64, // Byte-swapped
    FORMAT_UNKNOWN
};

#pragma pack(push, 1)
struct ManifestEntry {
    uint32_t offset;
    uint32_t size;
    char name[32];
    char type[8];
};
#pragma pack(pop)

// --- Kernel System Calls ---
static ssize_t safe_pread(int fd, void *buf, size_t count, off_t offset) {
    return syscall(SYS_pread64, fd, buf, count, offset);
}
static int safe_open(const char *pathname, int flags, mode_t mode) {
    return syscall(SYS_openat, AT_FDCWD, pathname, flags, mode);
}
static int safe_close(int fd) {
    return syscall(SYS_close, fd);
}

// Detects ROM format based on the first 4 bytes
RomFormat detect_format(int fd) {
    uint32_t magic = 0;
    if (safe_pread(fd, &magic, 4, 0) != 4) return FORMAT_UNKNOWN;

    if (magic == 0x80371240) return FORMAT_Z64;
    if (magic == 0x40123780) return FORMAT_N64;
    if (magic == 0x37804012) return FORMAT_V64;

    return FORMAT_UNKNOWN;
}

// Dynamically converts a 32-bit value based on ROM format
uint32_t read_u32_safe(int fd, off_t offset, RomFormat format) {
    uint32_t val = 0;
    if (safe_pread(fd, &val, 4, offset) != 4) return 0;

    switch (format) {
        case FORMAT_Z64: return __builtin_bswap32(val); // Swap Big to Little
        case FORMAT_V64: // Handle Byte-swapped
            return ((val & 0xFF00FF00) >> 8) | ((val & 0x00FF00FF) << 8);
        case FORMAT_N64: 
        default: return val; // Already Little-Endian
    }
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
JNIEXPORT void JNICALL Java_com_bkawrapper_OtrService_runNativeOtrGeneration(
    JNIEnv* env, jobject instance, jobject callbackObj, jint romFd, 
    jstring outDirPathStr, jstring manifestPathStr) {

    const char* outDirPath = env->GetStringUTFChars(outDirPathStr, NULL);
    const char* manifestPath = env->GetStringUTFChars(manifestPathStr, NULL);
    jclass callbackClass = env->GetObjectClass(callbackObj);
    jmethodID progressMid = env->GetMethodID(callbackClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    // 1. Detect Format
    RomFormat format = detect_format(romFd);
    if (format == FORMAT_UNKNOWN) {
        LOGE("Unknown ROM format. Aborting.");
        return;
    }
    LOGI("ROM Format Detected: %d", format);

    // 2. Load Manifest
    std::vector<ManifestEntry> manifest;
    int mFd = safe_open(manifestPath, O_RDONLY, 0);
    if (mFd != -1) {
        uint32_t mCount = 0;
        if (read(mFd, &mCount, 4) == 4) {
            manifest.resize(mCount);
            read(mFd, manifest.data(), mCount * sizeof(ManifestEntry));
        }
        safe_close(mFd);
    }

    // 3. Read Entry Count using dynamic swap
    uint32_t entryCount = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET, format);
    LOGI("Detected %u file entries in ROM FID table", entryCount);

    if (entryCount == 0 || entryCount > 15000) {
        LOGE("Invalid entry count (%u). Mismatch in ROM version or offset.", entryCount);
        return;
    }

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) return;

        uint32_t currentFileOffset = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET + 4 + (i * 4), format);
        uint32_t nextFileOffset    = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET + 4 + ((i + 1) * 4), format);

        uint32_t fileSize = (nextFileOffset > currentFileOffset) ? (nextFileOffset - currentFileOffset) : 0;

        char fileName[256];
        if (i < manifest.size()) {
            snprintf(fileName, sizeof(fileName), "%s", manifest[i].name);
        } else {
            snprintf(fileName, sizeof(fileName), "unknown/%04X.bin", i);
        }

        int percentage = (int)(((i + 1) * 100) / entryCount);

        if (fileSize > 0 && fileSize < 0x1000000) {
            char fullPath[512];
            snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
            ensure_directories(fullPath);

            uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
            if (compressedBuffer) {
                safe_pread(romFd, compressedBuffer, fileSize, currentFileOffset);
                
                uint32_t decompressedSize = 0;
                uint8_t* finalBuffer = decompress_rare_asset(compressedBuffer, fileSize, &decompressedSize);

                int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    syscall(SYS_write, outFd, (finalBuffer ? finalBuffer : compressedBuffer), (finalBuffer ? decompressedSize : fileSize));
                    safe_close(outFd);
                }
                if (finalBuffer) free(finalBuffer);
                free(compressedBuffer);
            }
        }

        jstring jName = env->NewStringUTF(fileName);
        env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        env->PopLocalFrame(NULL);
    }

    env->ReleaseStringUTFChars(outDirPathStr, outDirPath);
    env->ReleaseStringUTFChars(manifestPathStr, manifestPath);
}
}
