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
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, TAG, __VA_ARGS__)

// Fallback for alGlobals if not defined by the game source
#ifdef NO_GAME_SRC
    ALGlobals* alGlobals = nullptr;
#else
    extern "C" { extern ALGlobals* alGlobals; }
#endif

extern "C" {
    // Resource management functions (Always available in ultra/ tools/ folders)
    void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);
    
    // Low-level OS symbols
    extern void initInterruptTables();

    // Original game entry point - Only declared if source is present
    #ifndef NO_GAME_SRC
        void mainLoop(void);
    #endif
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    LOGI("Starting Native Game Boot (Verification Mode)...");

    // 1. Initialize Audio Globals
    if (alGlobals == nullptr) {
        size_t allocSize = (sizeof(ALGlobals) + 15) & ~15; 
        void* ptr = nullptr;
        if (posix_memalign(&ptr, 16, allocSize) == 0) {
            alGlobals = (ALGlobals*) ptr;
            memset(alGlobals, 0, allocSize);
            LOGI("Audio globals initialized at %p", alGlobals);
        }
    }

    // 2. Initialize HLE tables
    initInterruptTables();

    // 3. Setup Asset Management (Verifies OTR logic)
    const char* nativeOtrPath = nullptr;
    if (otrPath != nullptr) nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);

    if (nativeOtrPath != nullptr && assetManager != nullptr) {
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);
        AAsset* manifestAsset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);

        if (manifestAsset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*) AAsset_getBuffer(manifestAsset);
            uint32_t manifestSize = AAsset_getLength(manifestAsset);
            ResourceMgr_Init(nativeOtrPath, manifestBuf, manifestSize);
            LOGI("Resource Manager initialized. OTR Path: %s", nativeOtrPath);
        }
        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    }

    // 4. Enter Main Loop
    #ifdef NO_GAME_SRC
        LOGI("OTR/APK Verification Complete. Skipping mainLoop().");
    #else
        LOGI("Handing control to mainLoop()...");
        mainLoop();
    #endif
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    // Input stubs
}

} // extern "C"
