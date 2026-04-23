#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h> // Required for posix_memalign and malloc
#include <string.h> // Required for memset and memcpy

#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    // These are defined in your stubs.cpp and other bridge files
    extern ALGlobals* alGlobals;
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);
    extern void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);

    // Persistent JNI objects to facilitate communication with OtrService.java
    static jobject g_service_ref = nullptr;
    static jmethodID g_progress_mid = nullptr;
}

extern "C" {

/**
 * Initialize the JNI link to the OtrService.
 * This creates a Global Reference so the service isn't garbage collected
 * while the background thread is running.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject serviceObj) {
    if (g_service_ref != nullptr) {
        env->DeleteGlobalRef(g_service_ref);
    }
    g_service_ref = env->NewGlobalRef(serviceObj);

    jclass serviceClass = env->GetObjectClass(g_service_ref);
    g_progress_mid = env->GetMethodID(serviceClass, "updateOtrProgress", "(ILjava/lang/String;)V");
    
    LOGI("NativeBridge: JNI system initialized and Service GlobalRef created.");
}

/**
 * Entry point for the OTR asset extraction process.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint romFd, jobject assetManager, jstring outDir) {
    const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
    AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);

    // Load the assets_manifest.bin from the APK's assets folder
    AAsset* asset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);
    if (asset) {
        uint8_t* manifestBuf = (uint8_t*)AAsset_getBuffer(asset);
        uint32_t manifestSize = AAsset_getLength(asset);

        LOGI("Starting OTR generation for directory: %s", nativeOutDir);
        run_native_otr_generation_with_callback(env, g_service_ref, g_progress_mid, 
                                               romFd, manifestBuf, manifestSize, nativeOutDir);
        
        AAsset_close(asset);
    } else {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "Failed to open assets_manifest.bin!");
    }

    env->ReleaseStringUTFChars(outDir, nativeOutDir);
}

/**
 * Standard N64 boot sequence wrapper.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    LOGI("NativeBridge: Executing nativeGameBoot...");

    // Safe allocation of Audio Globals
    if (alGlobals == nullptr) {
        void* ptr = nullptr;
        // N64 Audio expects 16-byte alignment for structures
        if (posix_memalign(&ptr, 16, sizeof(ALGlobals)) == 0) {
            memset(ptr, 0, sizeof(ALGlobals));
            alGlobals = (ALGlobals*)ptr;
            LOGI("Audio globals allocated at %p", alGlobals);
        }
    }

    initInterruptTables();
    LOGI("NativeBridge: Boot sequence complete.");
}

}
