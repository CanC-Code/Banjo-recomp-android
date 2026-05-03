#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>
#include <vector>
#include <cstdio>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// --- Global JNI References ---
static JavaVM* g_jvm = nullptr;

// --- External Linkage to Resource Manager and OTR Builder ---
extern "C" {
    /**
     * Defined in resource_mgr.cpp
     */
    void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize);

    /**
     * Defined in otr_builder.cpp
     */
    void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                               int romFd, const char* outDirPath);
}

extern "C" {

/**
 * Initializes the global JVM reference.
 * Called from OtrService or MainActivity to set up the environment.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject context) {
    LOGI("NativeBridge: nativeInit called");
    env->GetJavaVM(&g_jvm);
    LOGI("NativeBridge: nativeInit complete");
}

/**
 * Entry point for starting the game engine after extraction is complete.
 * This function loads the manifest binary from the disk and initializes the Resource Manager.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    LOGI("NativeBridge: nativeGameBoot called");
    
    const char* otrPath = env->GetStringUTFChars(otrPathStr, nullptr);
    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);

    // 1. Locate and Load the Manifest
    // The manifest was copied to the same directory as the assets by OtrService.java
    // Check for both US and PAL variations
    std::string manifestPath = std::string(otrPath) + "/manifest_us.bin";
    FILE* f = fopen(manifestPath.c_str(), "rb");
    
    if (!f) {
        manifestPath = std::string(otrPath) + "/manifest_pal.bin";
        f = fopen(manifestPath.c_str(), "rb");
    }

    if (f) {
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        rewind(f);

        if (size > 0) {
            std::vector<uint8_t> buffer(size);
            fread(buffer.data(), 1, size, f);
            fclose(f);

            // 2. Initialize Resource Manager with the disk-based manifest
            ResourceMgr_Init(otrPath, buffer.data(), (uint32_t)size);
            LOGI("NativeBridge: Resource Manager initialized with manifest at %s", manifestPath.c_str());
        } else {
            fclose(f);
            LOGE("NativeBridge: Manifest file is empty.");
        }
    } else {
        LOGE("NativeBridge: Failed to locate manifest binary at %s", otrPath);
    }

    // 3. Trigger Game Engine Loop
    // This is where you call the recompiled Banjo-Kazooie entry point (e.g., bootproc)
    LOGI("NativeBridge: Asset mapping complete. Preparing engine start...");
    
    // TODO: Call your recompiled boot logic here
    // GameLoop_Start(assetMgr);

    env->ReleaseStringUTFChars(otrPathStr, otrPath);
}

/**
 * Surface and Input stubs for the Android lifecycle
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint width, jint height) {
    LOGI("NativeBridge: surfaceReady (%d x %d)", width, height);
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint unused) {
    // Logic for OpenGL/Vulkan texture updates
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    // Pass Android input events to the emulated N64 Controller
}

} // extern "C"
