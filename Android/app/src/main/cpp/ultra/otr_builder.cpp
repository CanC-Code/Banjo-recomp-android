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

enum RomFormat { FORMAT_Z64, FORMAT_N64, FORMAT_V64, FORMAT_UNKNOWN };

#pragma pack(push, 1)
struct ManifestEntry {
    uint32_t offset;
    uint32_t size;
    char name[32];
    char type[8];
};
#pragma pack(pop)

// Robust Endian-Safe ROM format detection
RomFormat detect_format(int fd) {
    uint8_t magic[4] = {0};
    syscall(SYS_pread64, fd, magic, 4, 0);
    
    if (magic[0] == 0x80 && magic[1] == 0x37 && magic[2] == 0x12 && magic[3] == 0x40) {
        return FORMAT_Z64; // Big-Endian
    }
    if (magic[0] == 0x40 && magic[1] == 0x12 && magic[2] == 0x37 && magic[3] == 0x80) {
        return FORMAT_N64; // Little-Endian (.n64)
    }
    if (magic[0] == 0x37 && magic[1] == 0x80 && magic[2] == 0x40 && magic[3] == 0x12) {
        return FORMAT_V64; // Byte-swapped
    }
    
    return FORMAT_UNKNOWN;
}

uint32_t read_u32_safe(int fd, off_t offset, RomFormat format) {
    uint32_t val = 0;
    syscall(SYS_pread64, fd, &val, 4, offset);
    switch (format) {
        case FORMAT_Z64: return __builtin_bswap32(val);
        case FORMAT_V64: return ((val & 0xFF00FF00) >> 8) | ((val & 0x00FF00FF) << 8);
        default: return val;
    }
}

void ensure_dir(const char* path) {
    char tmp[512];
    char* p = NULL;
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (p = tmp + 1; *p; p++) {
        if (*p == '/') { *p = 0; mkdir(tmp, 0777); *p = '/'; }
    }
}

extern "C" {
void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                               int romFd, const char* outDirPath, const char* manifestPath) {
    
    LOGI(">>> Named OTR Extraction Started (romFd: %d)", romFd);

    RomFormat format = detect_format(romFd);
    if (format == FORMAT_UNKNOWN) {
        LOGE("Unknown ROM format. Check your source file.");
        return;
    }

    std::vector<ManifestEntry> manifest;
    int mFd = open(manifestPath, O_RDONLY);
    if (mFd != -1) {
        uint32_t mCount = 0;
        if (read(mFd, &mCount, 4) == 4) {
            manifest.resize(mCount);
            read(mFd, manifest.data(), mCount * sizeof(ManifestEntry));
        }
        close(mFd);
    }

    uint32_t entryCount = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET, format);
    LOGI("Detected %u file entries in ROM FID table", entryCount);

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) return;

        uint32_t cur = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET + 4 + (i * 4), format);
        uint32_t nxt = read_u32_safe(romFd, ROM_FID_TABLE_OFFSET + 4 + ((i + 1) * 4), format);
        uint32_t size = (nxt > cur) ? (nxt - cur) : 0;

        char fileName[256];
        if (i < manifest.size()) {
            snprintf(fileName, sizeof(fileName), "%s", manifest[i].name);
        } else {
            snprintf(fileName, sizeof(fileName), "unknown/%04X.bin", i);
        }

        if (size > 0 && size < 0x1000000) {
            char fullPath[512];
            snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
            ensure_dir(fullPath);

            uint8_t* compressed = (uint8_t*)malloc(size);
            syscall(SYS_pread64, romFd, compressed, size, cur);
            
            uint32_t decompSize = 0;
            uint8_t* finalBuf = decompress_rare_asset(compressed, size, &decompSize);

            int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
            if (outFd != -1) {
                write(outFd, finalBuf ? finalBuf : compressed, finalBuf ? decompSize : size);
                close(outFd);
            }
            if (finalBuf) free(finalBuf);
            free(compressed);
        }

        if (i % 500 == 0) {
            int progress = (int)(((i + 1) * 100) / entryCount);
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, progress, jName);
        }
        env->PopLocalFrame(NULL);
    }
}
}
