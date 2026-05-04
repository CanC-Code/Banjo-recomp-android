#include <jni.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
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

RomFormat detect_format(uint8_t* magic) {
    if (magic[0] == 0x80 && magic[1] == 0x37 && magic[2] == 0x12 && magic[3] == 0x40) return FORMAT_Z64;
    if (magic[0] == 0x40 && magic[1] == 0x12 && magic[2] == 0x37 && magic[3] == 0x80) return FORMAT_N64;
    if (magic[0] == 0x37 && magic[1] == 0x80 && magic[2] == 0x40 && magic[3] == 0x12) return FORMAT_V64;
    return FORMAT_UNKNOWN;
}

// Convert Little-Endian (.n64) or Byte-Swapped (.v64) buffer into Native Big-Endian (.z64)
void normalize_rom_to_z64(uint8_t* romData, size_t size, RomFormat format) {
    if (format == FORMAT_N64) {
        for (size_t i = 0; i < (size & ~3); i += 4) {
            uint8_t t0 = romData[i];
            uint8_t t1 = romData[i+1];
            romData[i]   = romData[i+3];
            romData[i+1] = romData[i+2];
            romData[i+2] = t1;
            romData[i+3] = t0;
        }
    } else if (format == FORMAT_V64) {
        for (size_t i = 0; i < (size & ~1); i += 2) {
            uint8_t t = romData[i];
            romData[i]   = romData[i+1];
            romData[i+1] = t;
        }
    }
}

// Read 4 bytes from a normalized Z64 buffer and return as a host integer
uint32_t read_u32_be(uint8_t* buffer, uint32_t offset) {
    return (buffer[offset] << 24) | (buffer[offset+1] << 16) | (buffer[offset+2] << 8) | buffer[offset+3];
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

    // Get file size
    off_t romSize = lseek(romFd, 0, SEEK_END);
    lseek(romFd, 0, SEEK_SET);

    if (romSize < 0x1000000) { 
        LOGE("ROM is too small.");
        return;
    }

    // Load entire ROM into memory for rapid normalization and extraction
    uint8_t* romData = (uint8_t*)malloc(romSize);
    read(romFd, romData, romSize);

    RomFormat format = detect_format(romData);
    if (format == FORMAT_UNKNOWN) {
        LOGE("Unknown ROM format. Check your source file.");
        free(romData);
        return;
    }

    // Standardize all bits to Big-Endian to satisfy the Rareware decompression algorithm
    normalize_rom_to_z64(romData, romSize, format);
    LOGI("ROM Normalized to Z64 structure in memory.");

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

    uint32_t entryCount = read_u32_be(romData, ROM_FID_TABLE_OFFSET);
    LOGI("Detected %u file entries in ROM FID table", entryCount);

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) break;

        uint32_t cur = read_u32_be(romData, ROM_FID_TABLE_OFFSET + 4 + (i * 4));
        uint32_t nxt = read_u32_be(romData, ROM_FID_TABLE_OFFSET + 4 + ((i + 1) * 4));
        uint32_t size = (nxt > cur) ? (nxt - cur) : 0;

        char fileName[256];
        if (i < manifest.size()) {
            snprintf(fileName, sizeof(fileName), "%s", manifest[i].name);
        } else {
            snprintf(fileName, sizeof(fileName), "unknown/%04X.bin", i);
        }

        if (size > 0 && (cur + size) <= romSize) {
            char fullPath[512];
            snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
            ensure_dir(fullPath);

            uint8_t* compressed = romData + cur;
            uint32_t decompSize = 0;
            
            // Safe decompression from the newly normalized byte-stream
            uint8_t* finalBuf = decompress_rare_asset(compressed, size, &decompSize);

            int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
            if (outFd != -1) {
                write(outFd, finalBuf ? finalBuf : compressed, finalBuf ? decompSize : size);
                close(outFd);
            }
            if (finalBuf) free(finalBuf);
        }

        if (i % 500 == 0) {
            int progress = (int)(((i + 1) * 100) / entryCount);
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, progress, jName);
        }
        env->PopLocalFrame(NULL);
    }
    
    free(romData);
}
}
