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

static uint32_t read_u32_be(const uint8_t* ptr) {
    return ((uint32_t)ptr[0] << 24) |
           ((uint32_t)ptr[1] << 16) |
           ((uint32_t)ptr[2] << 8)  |
            (uint32_t)ptr[3];
}

// CRITICAL CORRECTION: Robust path building ensuring the final leaf node is always created
void ensure_directories(const char* path) {
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    size_t len = strlen(tmp);
    
    // Append a trailing slash if missing so the tokenizer catches the final directory
    if (len > 0 && tmp[len - 1] != '/') {
        strncat(tmp, "/", sizeof(tmp) - len - 1);
    }
    
    for (char* p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0777); // EEXIST is safely ignored natively
            *p = '/';
        }
    }
}

// --- 3. Absolutely Self-Building Engine ---
void run_native_otr_generation_internal(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                        int romFd, const char* outDirPath) {

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "STATUS: Loading ROM to memory...");
    debug_ui(env, callbackObj, progressMid, "STATUS: Loading ROM to RAM...");

    lseek(romFd, 0, SEEK_SET);
    std::vector<uint8_t> romData;
    uint8_t tempBuf[65536];
    ssize_t bRead;

    while ((bRead = read(romFd, tempBuf, sizeof(tempBuf))) > 0) {
        romData.insert(romData.end(), tempBuf, tempBuf + bRead);
    }

    if (romData.size() < 4096) {
        debug_ui(env, callbackObj, progressMid, "ERROR: ROM Read Failed.");
        return;
    }

    RomFormat format = detect_format_from_buffer(romData.data());
    if (format == FORMAT_UNKNOWN) {
        debug_ui(env, callbackObj, progressMid, "ERROR: Unknown ROM Format.");
        return;
    }

    normalize_entire_rom(romData, format);
    ensure_directories(outDirPath);

    // Dynamic ASetup Pattern Scanner
    uint32_t tableOffset = 0x5E98; // Fallback hard baseline for US v1.0
    uint32_t firstAssetOffset = 0x10CD0; 
    bool foundTable = false;

    for (uint32_t i = 0x5000; i < 0xA000; i += 4) {
        uint32_t entry1 = read_u32_be(romData.data() + i);
        uint32_t entry2 = read_u32_be(romData.data() + i + 4);
        uint32_t entry3 = read_u32_be(romData.data() + i + 8);
        
        // Validate sequential strict progression bounds unique to asset tables
        if (entry1 >= 0x10000 && entry2 > entry1 && entry3 > entry2 && entry3 < 0x20000) {
            tableOffset = i;
            firstAssetOffset = entry1;
            foundTable = true;
            break;
        }
    }

    if (!foundTable) {
        __android_log_print(ANDROID_LOG_WARN, LOG_TAG, "Scanner missed valid structure bounds. Relying on default offsets.");
    }

    // CRITICAL CORRECTION: Correct table measurement algorithm starting at zero.
    uint32_t entryCount = 0;
    uint32_t lastOffset = 0; // Fixed: Do not initialize to firstAssetOffset
    
    while (tableOffset + (entryCount * 4) < romData.size()) {
        uint32_t nextOffset = read_u32_be(romData.data() + tableOffset + (entryCount * 4));
        
        // Table ends when padding begins or pointers regress backwards
        if (nextOffset < lastOffset || nextOffset > romData.size() || nextOffset == 0) break;
        
        lastOffset = nextOffset;
        entryCount++;
    }

    if (entryCount == 0) {
        debug_ui(env, callbackObj, progressMid, "ERROR: Failed to locate ROM File Table.");
        return;
    }

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Found BK Asset Table at 0x%X. Total Files: %u", tableOffset, entryCount);

    uint32_t successCount = 0;
    int lastPercentage = -1;

    // CRITICAL CORRECTION: Iterate to entryCount - 1 so we can peek ahead at the next pointer
    // This accurately dictates the fileSize constraint for the current offset pointer.
    for (uint32_t i = 0; i < entryCount - 1; i++) {
        if (env->PushLocalFrame(16) < 0) break;

        uint32_t currentAssetOffset = read_u32_be(romData.data() + tableOffset + (i * 4));
        uint32_t nextAssetOffset    = read_u32_be(romData.data() + tableOffset + ((i + 1) * 4));
        
        if (nextAssetOffset < currentAssetOffset) {
            env->PopLocalFrame(NULL);
            break; 
        }

        uint32_t fileSize = nextAssetOffset - currentAssetOffset;

        if (currentAssetOffset + fileSize <= romData.size() && fileSize >= 2) {
            if (romData[currentAssetOffset] == 0x11 && romData[currentAssetOffset + 1] == 0x72) {
                uint32_t decompressedSize = 0;
                uint8_t* outBuf = decompress_rare_asset(romData.data() + currentAssetOffset, fileSize, &decompressedSize);

                if (outBuf) {
                    char fullPath[512];
                    snprintf(fullPath, sizeof(fullPath), "%s/asset_%08X.bin", outDirPath, currentAssetOffset);
                    
                    int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                    if (outFd != -1) {
                        write(outFd, outBuf, decompressedSize);
                        close(outFd);
                        successCount++;
                    } else {
                        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "File Write Failed: %s (%s)", fullPath, strerror(errno));
                    }
                    free(outBuf);
                }
            }
        }

        int percentage = (int)(((i + 1) * 100) / (entryCount - 1));
        if (percentage > lastPercentage || i == entryCount - 2) {
            lastPercentage = percentage;
            char uiMsg[64];
            snprintf(uiMsg, sizeof(uiMsg), "Extracted asset_%08X.bin", currentAssetOffset);
            jstring jName = env->NewStringUTF(uiMsg);
            env->CallVoidMethod(callbackObj, progressMid, percentage, jName);
            if (env->ExceptionCheck()) env->ExceptionClear();
            env->DeleteLocalRef(jName);
        }

        env->PopLocalFrame(NULL);
    }

    __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "Extraction complete. Processed %u compressed assets.", successCount);
    debug_ui(env, callbackObj, progressMid, "Extraction Complete! Booting...");
}

// --- 4. The JNI Bridge ---
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_OtrService_runNativeOtrGeneration(JNIEnv* env, jobject thiz, 
                                                      jobject callback, jint romFd, 
                                                      jstring outDir, jstring manifestPath) {

    const char* cOutDir = env->GetStringUTFChars(outDir, nullptr);

    jclass callbackClass = env->GetObjectClass(callback);
    jmethodID progressMid = env->GetMethodID(callbackClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    if (progressMid != nullptr) {
        run_native_otr_generation_internal(env, callback, progressMid, romFd, cOutDir);
    }

    env->ReleaseStringUTFChars(outDir, cOutDir);
}
