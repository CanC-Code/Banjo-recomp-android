#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>

#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    extern ALGlobals* alGlobals;
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);
    
    // Persistent JNI objects
    static jobject g_service_ref = nullptr;
    static jmethodID g_progress_mid = nullptr;
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject serviceObj) {
    // 1. Create a Global Reference so the service isn't deleted by Java
    if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
    g_service_ref = env->NewGlobalRef(serviceObj);

    // 2. Cache the callback method
    jclass serviceClass = env->GetObjectClass(g_service_ref);
    g_progress_mid = env->GetMethodID(serviceClass, "updateOtrProgress", "(ILjava/lang/String;)V");
    
    LOGI("NativeBridge: JNI Initialized with GlobalRef.");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint romFd, jobject assetManager, jstring outDir) {
    if (g_service_ref == nullptr) {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "Bridge not initialized! Call nativeInit first.");
        return;
    }

    const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
    AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);

    AAsset* asset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);
    if (asset != nullptr) {
        uint8_t* manifestBuf = (uint8_t*)AAsset_getBuffer(asset);
        uint32_t manifestSize = AAsset_getLength(asset);

        LOGI("Starting OTR generation...");
        run_native_otr_generation_with_callback(env, g_service_ref, g_progress_mid, 
                                               romFd, manifestBuf, manifestSize, nativeOutDir);
        
        AAsset_close(asset);
    } else {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "CRITICAL: assets_manifest.bin not found in APK assets!");
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
