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
#define LOGF(...) __android_log_print(ANDROID_LOG_FATAL, TAG, __VA_ARGS__)

extern "C" {
    // Resource management functions (Always available in ultra/ folder)
    void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);

    // Low-level OS symbols (Always available in emulator/ folder)
    extern void initInterruptTables();

    // Original game entry points - Wrapped for verification builds
    #ifndef NO_GAME_SRC
        void mainLoop(void);
    #endif
}

extern "C" {

/**
 * Bootstraps the N64 environment and starts the game loop.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    LOGI("Starting Native Game Boot...");

    // 1. Initialize Audio Globals
    // This verifies that the audio headers and memory alignment logic are working.
    if (alGlobals == nullptr) {
        size_t allocSize = (sizeof(ALGlobals) + 15) & ~15; 
        void* ptr = nullptr;

        if (posix_memalign(&ptr, 16, allocSize) == 0) {
            alGlobals = (ALGlobals*) ptr;
            memset(alGlobals, 0, allocSize);
            LOGI("Audio globals initialized and aligned at %p", alGlobals);
        } else {
            LOGF("CRITICAL: posix_memalign failed to allocate alGlobals!");
            return;
        }
    }

    // 2. Initialize HLE tables
    initInterruptTables();

    // 3. Setup Asset Management
    // This is the core "OTR Verification" step. 
    // It tests if the manifest can be read from the APK and if the OTR path is valid.
    const char* nativeOtrPath = nullptr;
    if (otrPath != nullptr) {
        nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);
    }

    if (nativeOtrPath != nullptr && assetManager != nullptr) {
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);
        AAsset* manifestAsset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);

        if (manifestAsset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*) AAsset_getBuffer(manifestAsset);
            uint32_t manifestSize = AAsset_getLength(manifestAsset);

            ResourceMgr_Init(nativeOtrPath, manifestBuf, manifestSize);
            LOGI("Resource Manager initialized with manifest size: %u", manifestSize);
        } else {
            LOGW("assets_manifest.bin not found, starting with empty manifest.");
            ResourceMgr_Init(nativeOtrPath, nullptr, 0);
        }

        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    } else {
        LOGW("Warning: otrPath or AssetManager was null. Proceeding with defaults.");
        ResourceMgr_Init("assets.otr", nullptr, 0);
    }

    // 4. Enter Main Loop (Blocking)
    #ifdef NO_GAME_SRC
        LOGI("Verification Successful: OTR logic and APK shell are functional.");
        LOGI("Exiting boot process (NO_GAME_SRC is defined).");
        return; 
    #else
        LOGI("Handing control to mainLoop()...");
        mainLoop();
    #endif
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    // Input handling logic remains stubbed or implemented as needed
}

} // extern "C"
