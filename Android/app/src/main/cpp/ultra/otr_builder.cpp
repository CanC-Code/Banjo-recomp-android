#include <jni.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <android/log.h>
#include <stdio.h>
#include <string.h>
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

void debug_ui(JNIEnv* env, jobject callbackObj, jmethodID progressMid, int p, const char* msg) {
    jstring jMsg = env->NewStringUTF(msg);
    env->CallVoidMethod(callbackObj, progressMid, p, jMsg);
    env->DeleteLocalRef(jMsg);
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

    FILE* mFile = fopen(cManifestPath, "rb");
    if (!mFile) {
        debug_ui(env, callback, progressMid, 0, "ERROR: Manifest missing");
        return;
    }

    uint32_t entryCount;
    fread(&entryCount, sizeof(uint32_t), 1, mFile);

    // Stream-based extraction
    for (uint32_t i = 0; i < entryCount; i++) {
        ManifestEntry entry;
        fread(&entry, sizeof(ManifestEntry), 1, mFile);

        // Seek directly to asset offset in the ROM file descriptor
        uint8_t* buffer = (uint8_t*)malloc(entry.size);
        pread(romFd, buffer, entry.size, entry.offset);

        // Identify Rare compression
        if (buffer[0] == 0x11 && buffer[1] == 0x72) {
            uint32_t outSize = 0;
            uint8_t* outBuf = decompress_rare_asset(buffer, entry.size, &outSize);
            if (outBuf) {
                char path[512];
                snprintf(path, 512, "%s/asset_%08X.bin", cOutDir, entry.offset);
                FILE* out = fopen(path, "wb");
                fwrite(outBuf, 1, outSize, out);
                fclose(out);
                free(outBuf);
            }
        }
        free(buffer);

        if (i % 10 == 0) {
            char status[64];
            snprintf(status, 64, "Processing: %s", entry.name);
            debug_ui(env, callback, progressMid, (i * 100) / entryCount, status);
        }
    }

    fclose(mFile);
    debug_ui(env, callback, progressMid, 100, "Extraction Complete!");
    env->ReleaseStringUTFChars(outDir, cOutDir);
    env->ReleaseStringUTFChars(manifestPath, cManifestPath);
}
