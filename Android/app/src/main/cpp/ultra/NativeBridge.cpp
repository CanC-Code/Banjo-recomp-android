#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>
#include <string>

// Include our custom types first
#include "n64_types.h"

// Wrap N64 headers in extern "C" so C++ understands they are C functions
extern "C" {
    #include "ultra64.h"
    #include "PR/sched.h"
    #include "PR/libaudio.h"
}

#define TAG "BKA-NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

// Corrected linkage for alGlobals
#ifdef NO_GAME_SRC
    // Use a different name for our stub to avoid collision with the header's extern
    ALGlobals* myAlGlobals = nullptr;
    #define alGlobals myAlGlobals
#else
    extern "C" { extern ALGlobals* alGlobals; }
#endif

extern "C" {
    void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);
    extern void initInterruptTables();

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
            // Using a cast to resolve the pointer
            *((ALGlobals**)&alGlobals) = (ALGlobals*)ptr;
            memset((void*)alGlobals, 0, allocSize);
            LOGI("Audio globals initialized.");
        }
    }

    initInterruptTables();

    const char* nativeOtrPath = nullptr;
    if (otrPath != nullptr) nativeOtrPath = env->GetStringUTFChars(otrPath, nullptr);

    if (nativeOtrPath != nullptr && assetManager != nullptr) {
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);
        AAsset* manifestAsset = AAssetManager_open(nativeAssetManager, "assets_manifest.bin", AASSET_MODE_BUFFER);

        if (manifestAsset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*) AAsset_getBuffer(manifestAsset);
            uint32_t manifestSize = AAsset_getLength(manifestAsset);
            ResourceMgr_Init(nativeOtrPath, manifestBuf, manifestSize);
            LOGI("Resource Manager initialized.");
        }
        env->ReleaseStringUTFChars(otrPath, nativeOtrPath);
    }

    #ifdef NO_GAME_SRC
        LOGI("Verification Complete. Skipping mainLoop().");
    #else
        mainLoop();
    #endif
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
}

}
