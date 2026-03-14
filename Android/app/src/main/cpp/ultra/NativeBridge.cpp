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
    void ResourceMgr_Init(const char* otrPath);
    
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
    // The original engine expects this pointer to be valid before any audio calls.
    if (alGlobals == nullptr) {
        alGlobals = malloc(sizeof(ALGlobals)); 
        memset(alGlobals, 0, sizeof(ALGlobals));
        LOGI("Audio globals initialized at %p", alGlobals);
    }

    // 2. Initialize Interrupt/Exception Tables (from exceptasm.cpp)
    initInterruptTables();
    LOGI("HLE Interrupt tables initialized.");

    // 3. Setup Asset Management (OTR)
    const char* nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);
    if (nativeOtrPath != nullptr) {
        LOGI("Initializing Resource Manager with OTR: %s", nativeOtrPath);
        ResourceMgr_Init(nativeOtrPath);
        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    }

    // 4. Enter Main Loop
    // WARNING: This call is BLOCKING. The Java side should call this 
    // inside a new Thread or it will hang the Android UI.
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
