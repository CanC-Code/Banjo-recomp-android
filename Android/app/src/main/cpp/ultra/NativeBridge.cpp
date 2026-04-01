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

    // Emulator/Resource management functions
    // FIX: Updated signature to match the actual implementation in resource_mgr.cpp
    void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);

    // Low-level OS symbols defined in exceptasm.cpp / setintmask.cpp
    extern void initInterruptTables();
    extern void* alGlobals;
}

extern "C" {

/**
 * Bootstraps the N64 environment and starts the game loop.
 * Usually called from a dedicated Worker or GL thread in Java.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    LOGI("Starting Native Game Boot...");

    // 1. Initialize Audio Globals
    // FIX: Ensure 16-byte alignment for N64 DMA engines using aligned_alloc.
    // Size must be rounded up to the nearest multiple of 16.
    if (alGlobals == nullptr) {
        size_t allocSize = (sizeof(ALGlobals) + 15) & ~15; 
        alGlobals = aligned_alloc(16, allocSize); 
        memset(alGlobals, 0, allocSize);
        LOGI("Audio globals initialized and aligned at %p", alGlobals);
    }

    // 2. Initialize Interrupt/Exception Tables (from exceptasm.cpp)
    initInterruptTables();
    LOGI("HLE Interrupt tables initialized.");

    // 3. Setup Asset Management (OTR)
    const char* nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);
    if (nativeOtrPath != nullptr) {
        LOGI("Initializing Resource Manager with OTR: %s", nativeOtrPath);
        
        // FIX: Properly extract the manifest buffer using the provided Java AssetManager
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);
        AAsset* manifestAsset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);
        
        if (manifestAsset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*) AAsset_getBuffer(manifestAsset);
            uint32_t manifestSize = AAsset_getLength(manifestAsset);
            
            // Pass the buffer and size to ResourceMgr_Init
            ResourceMgr_Init(nativeOtrPath, manifestBuf, manifestSize);
            
            // Note: We leave the asset open so the buffer remains valid in memory 
            // for the duration of the ResourceMgr's lifecycle.
        } else {
            __android_log_print(ANDROID_LOG_ERROR, TAG, "Failed to load assets_manifest.bin from APK assets");
            ResourceMgr_Init(nativeOtrPath, nullptr, 0); // Graceful fallback
        }

        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    }

    // 4. Enter Main Loop
    // WARNING: This call is BLOCKING.
    // Make sure the Java side calls this inside a new Thread, or it will hang the Android UI.
    LOGI("Handing control to mainLoop()...");
    mainLoop();
}

/**
 * Optional: Used to pass touch/controller inputs into the N64 OSCont structures.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    // Logic to update your __osCont (Controller) structures would go here.
}

} // extern "C"
