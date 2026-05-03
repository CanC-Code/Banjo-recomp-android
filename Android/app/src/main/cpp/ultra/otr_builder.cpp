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
    FORMAT_Z64, // Big-Endian
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

RomFormat detect_format(int fd) {
    uint32_t magic = 0;
    if (safe_pread(fd, &magic, 4, 0) != 4) return FORMAT_UNKNOWN;
    if (magic == 0x80371240) return FORMAT_Z64;
    if (magic == 0x40123780) return FORMAT_N64;
    if (magic == 0x37804012) return FORMAT_V64;
    return FORMAT_UNKNOWN;
}

uint32_t read_u32_safe(int fd, off_t offset, RomFormat format) {
    uint32_t val = 0;
    if (safe_pread(fd, &val, 4, offset) != 4) return 0;
    switch (format) {
        case FORMAT_Z64: return __builtin_bswap32(val);
        case FORMAT_V64: return ((val & 0xFF00FF00) >> 8) | ((val & 0x00FF00FF) << 8);
        default: return val;
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
/**
 * Standard C function called by NativeBridge.cpp
 * This provides the linkage the linker is currently missing.
 */
void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                               int romFd, const char* outDirPath, const char* manifestPath) {

    LOGI(">>> Named OTR Extraction Started (romFd: %d)", romFd);

    RomFormat format = detect_format(romFd);
    if (format == FORMAT_UNKNOWN) {
        LOGE("Unknown ROM format. Aborting extraction.");
        return;
    }
    LOGI("ROM Format Detected: %d", format);

    std::vector<ManifestEntry> manifest;
    int mFd = safe_open(manifestPath, O_RDONLY, 0);
    if (mFd != -1) {
        uint32_t mCount = 0;
        if (read(mFd, &mCount, 4) == 4) {
            manifest.resize(mCount);
            read(mFd, manifest.data(), mCount * sizeof(ManifestEntry));
            LOGI("Manifest loaded: %u entries", mCount);
        }
        safe_close(mFd);
    }

    uint32_t entryCount = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET, format);
    if (entryCount == 0 || entryCount > 15000) {
        LOGE("Invalid entry count: %u", entryCount);
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

        if (fileSize > 0 && fileSize < 0x1000000) {
            char fullPath[512];
            snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
            ensure_directories(fullPath);

            uint8_t* compressedBuffer = (uint8_t*)malloc(fileSize);
            if (compressedBuffer) {
                safe_pread(romFd, compressedBuffer, fileSize, currentFileOffset);
                uint32_t decompSize = 0;
                uint8_t* decompBuf = decompress_rare_asset(compressedBuffer, fileSize, &decompSize);

                int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                if (outFd != -1) {
                    write(outFd, decompBuf ? decompBuf : compressedBuffer, decompBuf ? decompSize : fileSize);
                    safe_close(outFd);
                }
                if (decompBuf) free(decompBuf);
                free(compressedBuffer);
            }
        }

        if (i % 100 == 0 || i == entryCount - 1) {
            int percentage = (int)(((i + 1) * 100) / entryCount);
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
        }
        env->PopLocalFrame(NULL);
    }
    LOGI("Extraction complete.");
}
}
