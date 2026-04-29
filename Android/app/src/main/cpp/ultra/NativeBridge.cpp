#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <GLES3/gl3.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>

// Include engine types AFTER JNI to prevent macro collisions
#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    // Engine globals and external functions
    extern ALGlobals* alGlobals;
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);

    static jobject g_service_ref = nullptr;
    static jmethodID g_progress_mid = nullptr;

    // --- JNI Implementations ---

    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject serviceObj) {
        if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
        g_service_ref = env->NewGlobalRef(serviceObj);

        jclass serviceClass = env->GetObjectClass(g_service_ref);
        g_progress_mid = env->GetMethodID(serviceClass, "updateOtrProgress", "(ILjava/lang/String;)V");
        LOGI("NativeBridge initialized.");
    }

    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint romFd, jobject assetManager, jstring outDir) {
        const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);

        AAsset* asset = AAssetManager_open(nativeAssetManager, "manifest_us.bin", AASSET_MODE_BUFFER);
        if (asset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*)AAsset_getBuffer(asset);
            uint32_t manifestSize = AAsset_getLength(asset);
            run_native_otr_generation_with_callback(env, g_service_ref, g_progress_mid, 
                                                   romFd, manifestBuf, manifestSize, nativeOutDir);
            AAsset_close(asset);
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
        LOGI("Engine Memory Booted! Waiting for GLRenderer to draw frames...");
    }

    /**
     * The Heartbeat: Updates the OpenGL texture with N64 frame data.
     * Called 60fps from the Android Choreographer/GLSurfaceView.
     */
    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint textureId) {
        if (alGlobals == nullptr) return;

        // 1. Bind the target texture
        glBindTexture(GL_TEXTURE_2D, textureId);

        // 2. Upload Pixel Data
        // Assumes a 320x240 buffer. Adjust resolution if your recomp uses 640x480.
        // alGlobals must point to a valid pixel array (usually uint32_t for RGBA)
        glTexSubImage2D(
            GL_TEXTURE_2D, 
            0,                  // Level
            0, 0,               // Offsets
            320, 240,           // Width, Height
            GL_RGBA,            // Pixel Format
            GL_UNSIGNED_BYTE,   // Data Type
            alGlobals           // Pointer to raw frame data
        );

        // 3. Unbind to stay clean
        glBindTexture(GL_TEXTURE_2D, 0);
    }
}
