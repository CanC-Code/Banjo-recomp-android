#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>
#include <string>

#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    // Original game entry points
    void mainLoop(void);

    // Resource management functions
    void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);

    // Low-level OS symbols
    extern void initInterruptTables();
    
    // FIX: Removed manual 'alGlobals' redeclaration. We now rely fully on libaudio.h!
}

extern "C" {

/**
 * Bootstraps the N64 environment and starts the game loop.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    LOGI("Starting Native Game Boot...");

    // 1. Initialize Audio Globals
    if (alGlobals == nullptr) {
        size_t allocSize = (sizeof(ALGlobals) + 15) & ~15; 
        void* ptr = nullptr;
        
        // posix_memalign returns 0 on success
        if (posix_memalign(&ptr, 16, allocSize) == 0) {
            alGlobals = (ALGlobals*) ptr;
            memset(alGlobals, 0, allocSize);
            LOGI("Audio globals initialized and aligned at %p", alGlobals);
        } else {
            __android_log_print(ANDROID_LOG_FATAL, TAG, "CRITICAL: posix_memalign failed to allocate alGlobals!");
            return;
        }
    }

    // 2. Initialize HLE tables
    initInterruptTables();

    // 3. Setup Asset Management
    const char* nativeOtrPath = nullptr;
    if (otrPath != nullptr) {
        nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);
    }
    
    // Safety check in case Java passes nulls through the thread
    if (nativeOtrPath != nullptr && assetManager != nullptr) {
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);
        AAsset* manifestAsset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);
        
        if (manifestAsset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*) AAsset_getBuffer(manifestAsset);
            uint32_t manifestSize = AAsset_getLength(manifestAsset);
            
            ResourceMgr_Init(nativeOtrPath, manifestBuf, manifestSize);
            LOGI("Resource Manager initialized with manifest size: %u", manifestSize);
        } else {
            __android_log_print(ANDROID_LOG_WARN, TAG, "assets_manifest.bin not found, starting with empty manifest.");
            ResourceMgr_Init(nativeOtrPath, nullptr, 0);
        }

        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    } else {
        __android_log_print(ANDROID_LOG_WARN, TAG, "Warning: otrPath or AssetManager was null. Proceeding with defaults.");
        ResourceMgr_Init("assets.otr", nullptr, 0);
    }

    // 4. Enter Main Loop (Blocking)
    LOGI("Handing control to mainLoop()...");
    mainLoop();
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    // Input handling logic goes here
}

} // extern "C"
