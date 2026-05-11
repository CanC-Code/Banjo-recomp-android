#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <android/log.h>
#include <stdio.h>
#include "rare_decompression.h"

#define LOG_TAG "BKA_OTR"

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

// --- 2. Endianness Window Logic ---
enum RomFormat { FORMAT_Z64, FORMAT_N64, FORMAT_V64, FORMAT_UNKNOWN };

static RomFormat detect_format(int romFd) {
    uint8_t magic[4] = {0};
    safe_pread(romFd, magic, 4, 0);
    if (magic[0] == 0x80 && magic[1] == 0x37 && magic[2] == 0x12 && magic[3] == 0x40) return FORMAT_Z64;
    if (magic[0] == 0x40 && magic[1] == 0x12 && magic[2] == 0x37 && magic[3] == 0x80) return FORMAT_N64;
    if (magic[0] == 0x37 && magic[1] == 0x80 && magic[2] == 0x40 && magic[3] == 0x12) return FORMAT_V64;
    return FORMAT_UNKNOWN;
}

static void normalize_chunk(uint8_t* data, size_t size, RomFormat format) {
    if (format == FORMAT_N64) {
        for (size_t i = 0; i < (size & ~3); i += 4) {
            uint8_t t0 = data[i]; uint8_t t1 = data[i+1];
            data[i] = data[i+3]; data[i+1] = data[i+2];
            data[i+2] = t1; data[i+3] = t0;
        }
    } else if (format == FORMAT_V64) {
        for (size_t i = 0; i < (size & ~1); i += 2) {
            uint8_t t = data[i]; data[i] = data[i+1]; data[i+1] = t;
        }
    }
}

// --- 3. Visual Debugger Helper ---
void debug_ui(JNIEnv* env, jobject callbackObj, jmethodID progressMid, const char* msg) {
    if (!env || !callbackObj || !progressMid) return;
    jstring jMsg = env->NewStringUTF(msg);
    env->CallVoidMethod(callbackObj, progressMid, 0, jMsg);
    env->DeleteLocalRef(jMsg);
}

// --- 4. Endian-Aware Data Readers ---
static uint32_t read_u32_le(const uint8_t* ptr) {
    return  (uint32_t)ptr[0]        |
           ((uint32_t)ptr[1] << 8)  |
           ((uint32_t)ptr[2] << 16) |
           ((uint32_t)ptr[3] << 24);
}

static uint32_t read_u32_be(const uint8_t* ptr) {
    return ((uint32_t)ptr[0] << 24) |
           ((uint32_t)ptr[1] << 16) |
           ((uint32_t)ptr[2] << 8)  |
            (uint32_t)ptr[3];
}

void ensure_directories(const char* path) {
    char tmp[512];
    int i = 0;
    while(path[i] != '\0' && i < 511) { tmp[i] = path[i]; i++; }
    tmp[i] = '\0';
    for (char* p = tmp + 1; *p; p++) {
        if (*p == '/') { *p = 0; mkdir(tmp, 0777); *p = '/'; }
    }
}

extern "C" {
void JNICALL run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                           int romFd, uint8_t* manifestPtr, uint32_t manifestSize,
                                           const char* outDirPath) {

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "STATUS: Initializing extraction...");
    debug_ui(env, callbackObj, progressMid, "STATUS: Initializing extraction...");

    RomFormat format = detect_format(romFd);
    if (format == FORMAT_UNKNOWN) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "ERROR: Unknown ROM Format.");
        debug_ui(env, callbackObj, progressMid, "ERROR: Unknown ROM Format.");
        return;
    }

    if (manifestSize < 4) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "ERROR: Manifest too small (%u bytes).", manifestSize);
        debug_ui(env, callbackObj, progressMid, "ERROR: Manifest too small.");
        return;
    }

    const uint32_t RECORD_SIZE = 48;
    const uint32_t maxPossible = (manifestSize - 4) / RECORD_SIZE;

    uint32_t entryCount = read_u32_le(manifestPtr);
    bool isLittleEndian = true;

    if (entryCount > maxPossible) {
        uint32_t beCount = read_u32_be(manifestPtr);
        if (beCount <= maxPossible) {
            entryCount = beCount;
            isLittleEndian = false;
        } else {
            char errMsg[160];
            snprintf(errMsg, sizeof(errMsg),
                "ERROR: Manifest corrupt — entry count invalid in both endiannesses "
                "(LE=%u, BE=%u, max possible=%u)",
                entryCount, beCount, maxPossible);
            __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "%s", errMsg);
            debug_ui(env, callbackObj, progressMid, errMsg);
            return;
        }
    }

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Detected %u entries. LittleEndian=%d, ManifestSize=%u",
                        entryCount, isLittleEndian, manifestSize);

    if (entryCount > (manifestSize - 4) / RECORD_SIZE) {
        char errMsg[128];
        snprintf(errMsg, sizeof(errMsg), "ERROR: OOB! Count:%u requires %llu bytes, but Size:%u",
                 entryCount, (unsigned long long)entryCount * RECORD_SIZE + 4, manifestSize);
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "%s", errMsg);
        debug_ui(env, callbackObj, progressMid, errMsg);
        return;
    }

    uint8_t* recordStart = manifestPtr + 4;
    uint32_t successCount = 0;

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) return;

        uint8_t* record = recordStart + (i * RECORD_SIZE);

        uint32_t romOffset = isLittleEndian ? read_u32_le(record + 0) : read_u32_be(record + 0);
        uint32_t fileSize  = isLittleEndian ? read_u32_le(record + 4) : read_u32_be(record + 4);

        char fileName[33];
        for(int j = 0; j < 32; j++) {
            uint8_t ch = *(record + 8 + j);
            // Allow '/' to preserve nested directory structures required by the engine
            if (ch >= 0x20 && ch < 0x7F && ch != '\\') {
                fileName[j] = (char)ch;
            } else if (ch == '\0') {
                for(int k = j; k < 32; k++) fileName[k] = '\0';
                break;
            } else {
                fileName[j] = '_';
            }
        }
        fileName[32] = '\0';

        if (fileName[0] == '\0' || fileSize == 0) {
            env->PopLocalFrame(NULL);
            continue;
        }

        char fullPath[512];
        int written = snprintf(fullPath, sizeof(fullPath), "%s/%s", outDirPath, fileName);
        if (written < 0 || written >= (int)sizeof(fullPath)) {
            env->PopLocalFrame(NULL);
            continue;
        }
        ensure_directories(fullPath);

        uint32_t alignedStart = romOffset & ~3u;
        uint32_t alignedEnd   = (romOffset + fileSize + 3) & ~3u;
        uint32_t alignedSize  = alignedEnd - alignedStart;

        if (alignedSize > 0) {
            uint8_t* workBuffer = (uint8_t*)::malloc(alignedSize);
            if (workBuffer) {
                if (safe_pread(romFd, workBuffer, alignedSize, alignedStart) == (ssize_t)alignedSize) {

                    normalize_chunk(workBuffer, alignedSize, format);
                    uint8_t* assetPtr = workBuffer + (romOffset - alignedStart);
                    uint32_t decompressedSize = 0;

                    uint8_t* finalBuffer = decompress_rare_asset(assetPtr, fileSize, &decompressedSize);

                    uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : assetPtr;
                    uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

                    int outFd = safe_open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                    if (outFd != -1) {
                        safe_write(outFd, writePtr, writeSize);
                        safe_close(outFd);
                        successCount++;
                    }
                    if (finalBuffer) ::free(finalBuffer);
                }
                ::free(workBuffer);
            }
        }

        if (i % 250 == 0 || i == entryCount - 1) {
            int percentage = (int)(((i + 1) * 100) / entryCount);
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
            env->DeleteLocalRef(jName);
        }

        env->PopLocalFrame(NULL);
    }

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Extraction complete. Processed %u assets.", successCount);
    debug_ui(env, callbackObj, progressMid, "Extraction Complete! Booting...");
}
}
