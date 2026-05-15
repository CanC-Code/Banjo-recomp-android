#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <android/log.h>
#include <stdio.h>
#include <string.h>
#include <vector>
#include "rare_decompression.h"

#define LOG_TAG "BKA_OTR"

// --- 1. Endianness Window Logic ---
enum RomFormat { FORMAT_Z64, FORMAT_N64, FORMAT_V64, FORMAT_UNKNOWN };

static RomFormat detect_format_from_buffer(const uint8_t* magic) {
    if (magic[0] == 0x80 && magic[1] == 0x37 && magic[2] == 0x12 && magic[3] == 0x40) return FORMAT_Z64;
    if (magic[0] == 0x40 && magic[1] == 0x12 && magic[2] == 0x37 && magic[3] == 0x80) return FORMAT_N64;
    if (magic[0] == 0x37 && magic[1] == 0x80 && magic[2] == 0x40 && magic[3] == 0x12) return FORMAT_V64;
    return FORMAT_UNKNOWN;
}

static void normalize_entire_rom(std::vector<uint8_t>& data, RomFormat format) {
    if (format == FORMAT_N64) {
        for (size_t i = 0; i < (data.size() & ~3); i += 4) {
            uint8_t t0 = data[i]; uint8_t t1 = data[i+1];
            data[i] = data[i+3]; data[i+1] = data[i+2];
            data[i+2] = t1; data[i+3] = t0;
        }
    } else if (format == FORMAT_V64) {
        for (size_t i = 0; i < (data.size() & ~1); i += 2) {
            uint8_t t = data[i]; data[i] = data[i+1]; data[i+1] = t;
        }
    }
}

// --- 2. Visual Debugger Helper ---
void debug_ui(JNIEnv* env, jobject callbackObj, jmethodID progressMid, const char* msg) {
    if (!env || !callbackObj || !progressMid) return;
    jstring jMsg = env->NewStringUTF(msg);
    env->CallVoidMethod(callbackObj, progressMid, 0, jMsg);

    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(jMsg);
}

// --- 3. Endian-Aware Data Readers ---
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

// --- 4. Core Extraction Engine ---
void run_native_otr_generation_internal(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize,
                                        const char* outDirPath) {

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "STATUS: Loading ROM to memory...");
    debug_ui(env, callbackObj, progressMid, "STATUS: Loading ROM to RAM...");

    // 1. Safe rewind and load entire ROM into RAM
    lseek(romFd, 0, SEEK_SET);
    std::vector<uint8_t> romData;
    uint8_t tempBuf[65536];
    ssize_t bRead;

    while ((bRead = read(romFd, tempBuf, sizeof(tempBuf))) > 0) {
        romData.insert(romData.end(), tempBuf, tempBuf + bRead);
    }

    if (romData.size() < 4096) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "ERROR: ROM file read failed.");
        debug_ui(env, callbackObj, progressMid, "ERROR: ROM Read Failed.");
        return;
    }

    RomFormat format = detect_format_from_buffer(romData.data());
    if (format == FORMAT_UNKNOWN) {
        debug_ui(env, callbackObj, progressMid, "ERROR: Unknown ROM Format.");
        return;
    }

    normalize_entire_rom(romData, format);

    if (manifestSize < 4) {
        debug_ui(env, callbackObj, progressMid, "ERROR: Manifest too small.");
        return;
    }

    // FIXED: Record size mathematically matched to struct footprint (4 + 4 + 32 = 40)
    // Prevents offset shifting and out-of-bounds extraction mapping.
    const uint32_t RECORD_SIZE = 40; 
    
    const uint32_t maxPossible = (manifestSize - 4) / RECORD_SIZE;
    uint32_t entryCount = read_u32_le(manifestPtr);
    bool isLittleEndian = true;

    if (entryCount > maxPossible) {
        uint32_t beCount = read_u32_be(manifestPtr);
        if (beCount <= maxPossible) {
            entryCount = beCount;
            isLittleEndian = false;
        } else {
            debug_ui(env, callbackObj, progressMid, "ERROR: Manifest Corrupt.");
            return;
        }
    }

    uint8_t* recordStart = manifestPtr + 4;
    uint32_t successCount = 0;
    char lastCreatedDir[512] = {0}; 
    int lastPercentage = -1; // Throttling variable

    for (uint32_t i = 0; i < entryCount; i++) {
        if (env->PushLocalFrame(16) < 0) return;

        uint8_t* record = recordStart + (i * RECORD_SIZE);
        uint32_t romOffset = isLittleEndian ? read_u32_le(record + 0) : read_u32_be(record + 0);
        uint32_t fileSize  = isLittleEndian ? read_u32_le(record + 4) : read_u32_be(record + 4);

        char fileName[33];
        for(int j = 0; j < 32; j++) {
            uint8_t ch = *(record + 8 + j);
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

        // 2. Directory Caching
        char dirOnly[512];
        const char* lastSlash = strrchr(fullPath, '/');
        if (lastSlash) {
            size_t dirLen = lastSlash - fullPath;
            if (dirLen < sizeof(dirOnly)) {
                strncpy(dirOnly, fullPath, dirLen);
                dirOnly[dirLen] = '\0';

                if (strcmp(dirOnly, lastCreatedDir) != 0) {
                    ensure_directories(fullPath);
                    strncpy(lastCreatedDir, dirOnly, sizeof(lastCreatedDir));
                }
            }
        }

        // 3. 64-bit Overflow Bounds Checking 
        if ((uint64_t)romOffset + (uint64_t)fileSize <= (uint64_t)romData.size()) {
            uint8_t* assetPtr = romData.data() + romOffset;
            uint32_t decompressedSize = 0;

            uint8_t* finalBuffer = decompress_rare_asset(assetPtr, fileSize, &decompressedSize);

            uint8_t* writePtr = (finalBuffer != nullptr) ? finalBuffer : assetPtr;
            uint32_t writeSize = (finalBuffer != nullptr) ? decompressedSize : fileSize;

            int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
            if (outFd != -1) {
                write(outFd, writePtr, writeSize);
                close(outFd);
                successCount++;
            }
            if (finalBuffer) ::free(finalBuffer);
        }

        // 4. UI Rate Limiter - strictly 1 update per whole percentage change
        int percentage = (int)(((i + 1) * 100) / entryCount);
        if (percentage > lastPercentage || i == entryCount - 1) {
            lastPercentage = percentage;
            jstring jName = env->NewStringUTF(fileName);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jName);

            if (env->ExceptionCheck()) env->ExceptionClear(); 
            env->DeleteLocalRef(jName);
        }

        env->PopLocalFrame(NULL);
    }

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Extraction complete. Processed %u assets.", successCount);
    debug_ui(env, callbackObj, progressMid, "Extraction Complete! Booting...");
}

// --- 5. The JNI Bridge ---
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_OtrService_runNativeOtrGeneration(JNIEnv* env, jobject thiz, 
                                                      jobject callback, jint romFd, 
                                                      jstring outDir, jstring manifestPath) {

    const char* cOutDir = env->GetStringUTFChars(outDir, nullptr);
    const char* cManifestPath = env->GetStringUTFChars(manifestPath, nullptr);

    jclass callbackClass = env->GetObjectClass(callback);
    jmethodID progressMid = env->GetMethodID(callbackClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    if (progressMid == nullptr) {
        env->ReleaseStringUTFChars(outDir, cOutDir);
        env->ReleaseStringUTFChars(manifestPath, cManifestPath);
        return;
    }

    int mfd = open(cManifestPath, O_RDONLY);
    if (mfd < 0) {
        debug_ui(env, callback, progressMid, "ERROR: Could not open manifest file on disk.");
        env->ReleaseStringUTFChars(outDir, cOutDir);
        env->ReleaseStringUTFChars(manifestPath, cManifestPath);
        return;
    }

    struct stat st;
    fstat(mfd, &st);
    uint32_t mSize = (uint32_t)st.st_size;

    if (mSize > 0) {
        uint8_t* mPtr = (uint8_t*)malloc(mSize);
        if (mPtr != nullptr) {
            pread(mfd, mPtr, mSize, 0);
            run_native_otr_generation_internal(env, callback, progressMid, romFd, mPtr, mSize, cOutDir);
            free(mPtr);
        } else {
            debug_ui(env, callback, progressMid, "ERROR: Failed to allocate memory for manifest.");
        }
    }

    close(mfd);
    env->ReleaseStringUTFChars(outDir, cOutDir);
    env->ReleaseStringUTFChars(manifestPath, cManifestPath);
}
