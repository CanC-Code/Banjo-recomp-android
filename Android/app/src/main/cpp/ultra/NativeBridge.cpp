#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>

#include "n64_types.h"

extern "C" {
    #include "ultra64.h"
    // alGlobals is defined in our stubs.cpp
    extern ALGlobals* alGlobals; 
    extern void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);
    extern void initInterruptTables();
}

#define TAG "BKA-NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    LOGI("Starting Native Game Boot...");

    // 1. Safe Audio Globals Init
    if (alGlobals == nullptr) {
        // Allocate 16-byte aligned memory for N64 audio structures
        void* ptr = nullptr;
        if (posix_memalign(&ptr, 16, sizeof(ALGlobals)) == 0) {
            memset(ptr, 0, sizeof(ALGlobals));
            alGlobals = (ALGlobals*)ptr;
            LOGI("Audio globals initialized at %p", alGlobals);
        }
    }

    initInterruptTables();

    // 2. Resource Manager Setup
    if (otrPath != nullptr && assetManager != nullptr) {
        const char* nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);
        
        // Open the manifest we included in the APK assets
        AAsset* manifestAsset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);

        if (manifestAsset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*) AAsset_getBuffer(manifestAsset);
            uint32_t manifestSize = AAsset_getLength(manifestAsset);
            ResourceMgr_Init(nativeOtrPath, manifestBuf, manifestSize);
            LOGI("Resource Manager initialized.");
        }
        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    }

    LOGI("Boot Sequence Complete.");
}
}
