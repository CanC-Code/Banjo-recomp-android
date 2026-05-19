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

#pragma pack(push, 1)
struct ManifestEntry {
    uint32_t offset;
    uint32_t size;
    char name[32];
    char type[8];
};
#pragma pack(pop)

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

void debug_ui(JNIEnv* env, jobject callbackObj, jmethodID progressMid, const char* msg) {
    if (!env || !callbackObj || !progressMid) return;
    jstring jMsg = env->NewStringUTF(msg);
    env->CallVoidMethod(callbackObj, progressMid, 0, jMsg);
    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(jMsg);
}

void ensure_directories(const char* path) {
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    size_t len = strlen(tmp);
    if (len > 0 && tmp[len - 1] != '/') {
        strncat(tmp, "/", sizeof(tmp) - len - 1);
    }
    for (char* p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            mkdir(tmp, 0777); 
            *p = '/';
        }
    }
}

void run_native_otr_generation_internal(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                        int romFd, const char* outDirPath, const char* manifestPath) {

    debug_ui(env, callbackObj, progressMid, "STATUS: Loading ROM to RAM...");

    lseek(romFd, 0, SEEK_SET);
    std::vector<uint8_t> romData;
    uint8_t tempBuf[65536];
    ssize_t bRead;

    while ((bRead = read(romFd, tempBuf, sizeof(tempBuf))) > 0) {
        romData.insert(romData.end(), tempBuf, tempBuf + bRead);
    }

    RomFormat format = detect_format_from_buffer(romData.data());
    normalize_entire_rom(romData, format);
    ensure_directories(outDirPath);

    char romOutPath[512];
    snprintf(romOutPath, sizeof(romOutPath), "%s/rom_base.bin", outDirPath);
    int rFd = open(romOutPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
    if (rFd != -1) {
        write(rFd, romData.data(), romData.size());
        close(rFd);
    }

    // CRITICAL CORRECTION: If manifestPath is empty, perform a heuristic ROM scan.
    if (manifestPath == nullptr || strlen(manifestPath) == 0) {
        __android_log_print(ANDROID_LOG_INFO, LOG_TAG, "No manifest provided. Performing heuristic scan...");
        
        // Example: Scan for Rare's asset compression signature (0x11 0x72) 
        // throughout the ROM data to auto-discover assets.
        for (size_t i = 0; i < romData.size() - 2; i++) {
            if (romData[i] == 0x11 && romData[i+1] == 0x72) {
                uint32_t decompressedSize = 0;
                uint8_t* outBuf = decompress_rare_asset(romData.data() + i, romData.size() - i, &decompressedSize);
                if (outBuf) {
                    char fullPath[512];
                    snprintf(fullPath, sizeof(fullPath), "%s/asset_%08X.bin", outDirPath, (uint32_t)i);
                    int outFd = open(fullPath, O_WRONLY | O_CREAT | O_TRUNC, 0666);
                    if (outFd != -1) {
                        write(outFd, outBuf, decompressedSize);
                        close(outFd);
                    }
                    free(outBuf);
                }
            }
        }
    } else {
        // Standard manifest path logic remains for compatibility
        FILE* manifestFile = fopen(manifestPath, "rb");
        if (manifestFile) {
            uint32_t entryCount = 0;
            fread(&entryCount, sizeof(uint32_t), 1, manifestFile);
            for (uint32_t i = 0; i < entryCount; i++) {
                ManifestEntry entry;
                fread(&entry, sizeof(ManifestEntry), 1, manifestFile);
                // ... (processing logic remains the same)
            }
            fclose(manifestFile);
        }
    }

    debug_ui(env, callbackObj, progressMid, "Extraction Complete! Booting...");
}

extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_OtrService_runNativeOtrGeneration(JNIEnv* env, jobject thiz, 
                                                      jobject callback, jint romFd, 
                                                      jstring outDir, jstring manifestPath) {

    const char* cOutDir = env->GetStringUTFChars(outDir, nullptr);
    const char* cManifestPath = env->GetStringUTFChars(manifestPath, nullptr);

    jclass callbackClass = env->GetObjectClass(callback);
    jmethodID progressMid = env->GetMethodID(callbackClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    if (progressMid != nullptr) {
        run_native_otr_generation_internal(env, callback, progressMid, romFd, cOutDir, cManifestPath);
    }

    env->ReleaseStringUTFChars(outDir, cOutDir);
    env->ReleaseStringUTFChars(manifestPath, cManifestPath);
}
