#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>
#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    extern ALGlobals* alGlobals;
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);

    // We will define this new function to parse the ROM dynamically
    extern bool GenerateManifestFromROM(int romFd, uint8_t** outManifestBuf, uint32_t* outManifestSize);

    static jobject g_service_ref = nullptr;
    static jmethodID g_progress_mid = nullptr;
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject serviceObj) {
    if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
    g_service_ref = env->NewGlobalRef(serviceObj);

    jclass serviceClass = env->GetObjectClass(g_service_ref);
    g_progress_mid = env->GetMethodID(serviceClass, "updateOtrProgress", "(ILjava/lang/String;)V");
    LOGI("NativeBridge initialized.");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint romFd, jobject assetManager, jstring outDir) {
    const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
    LOGI("runOtrGeneration: Starting dynamic manifest generation from ROM...");

    uint8_t* dynamicManifestBuf = nullptr;
    uint32_t dynamicManifestSize = 0;

    // 1. DYNAMICALLY GENERATE THE MANIFEST IN RAM
    if (GenerateManifestFromROM(romFd, &dynamicManifestBuf, &dynamicManifestSize)) {
        LOGI("Dynamic Manifest successfully generated! Size: %u", dynamicManifestSize);
        
        // 2. EXTRACT THE OTR FILES USING THE IN-MEMORY MANIFEST
        run_native_otr_generation_with_callback(env, g_service_ref, g_progress_mid, 
                                               romFd, dynamicManifestBuf, dynamicManifestSize, nativeOutDir);
        
        // Clean up the RAM buffer after extraction is done
        free(dynamicManifestBuf);
    } else {
        LOGE("CRITICAL ERROR: Failed to generate manifest from the provided ROM. Is it a valid Banjo-Kazooie ROM?");
    }

    env->ReleaseStringUTFChars(outDir, nativeOutDir);
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    if (alGlobals == nullptr) {
        void* ptr = nullptr;
        if (posix_memalign(&ptr, 16, sizeof(ALGlobals)) == 0) {
            memset(ptr, 0, sizeof(ALGlobals));
            alGlobals = (ALGlobals*)ptr;
        }
    }
    initInterruptTables();
}

}
