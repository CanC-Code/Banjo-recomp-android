#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <GLES3/gl3.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>

// Include engine types AFTER JNI to avoid macro pollution
#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    // --- Engine Externs ---
    // These link to symbols defined in your recompilation's C/C++ core
    extern ALGlobals* alGlobals;
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);

    // Static references for JNI callbacks
    static jobject g_service_ref = nullptr;
    static jmethodID g_progress_mid = nullptr;

    // --- JNI Implementation ---

    /**
     * Initializes the bridge and stores a reference to the Android Service.
     */
    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject serviceObj) {
        if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
        g_service_ref = env->NewGlobalRef(serviceObj);

        jclass serviceClass = env->GetObjectClass(g_service_ref);
        g_progress_mid = env->GetMethodID(serviceClass, "updateOtrProgress", "(ILjava/lang/String;)V");
        LOGI("NativeBridge: Initialized with Service reference.");
    }

    /**
     * Triggers the OTR (Optimized Texture Resource) generation process.
     */
    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint romFd, jobject assetManager, jstring outDir) {
        const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
        AAssetManager* nativeAssetManager = AAssetManager_fromJava(env, assetManager);

        // Load the OTR manifest from Android assets
        AAsset* asset = AAssetManager_open(nativeAssetManager, "manifest_us.bin", AASSET_MODE_BUFFER);
        if (asset != nullptr) {
            uint8_t* manifestBuf = (uint8_t*)AAsset_getBuffer(asset);
            uint32_t manifestSize = AAsset_getLength(asset);
            
            run_native_otr_generation_with_callback(env, g_service_ref, g_progress_mid, 
                                                   romFd, manifestBuf, manifestSize, nativeOutDir);
            AAsset_close(asset);
        } else {
            LOGE("NativeBridge: Failed to open manifest_us.bin from assets.");
        }
        env->ReleaseStringUTFChars(outDir, nativeOutDir);
    }

    /**
     * Allocates engine memory and boots the internal systems.
     */
    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
        if (alGlobals == nullptr) {
            void* ptr = nullptr;
            // Align memory to 16-bytes for N64/ARM64 performance compatibility
            if (posix_memalign(&ptr, 16, sizeof(ALGlobals)) == 0) {
                memset(ptr, 0, sizeof(ALGlobals));
                alGlobals = (ALGlobals*)ptr;
            }
        }

        initInterruptTables();
        LOGI("NativeBridge: Engine Memory Booted. Ready for frames.");
    }

    /**
     * The Main Render Loop Call.
     * Synchronizes the N64 framebuffer with the Android OpenGL texture.
     */
    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint textureId) {
        // Safety: Ensure engine is booted and the pixel buffer exists
        if (alGlobals == nullptr || alGlobals->screenBuffer == nullptr) {
            return;
        }

        // 1. Bind the texture ID passed from Java (GLRenderer.java)
        glBindTexture(GL_TEXTURE_2D, textureId);

        // 2. Push the raw pixels from N64 RAM to GPU VRAM
        // Assuming 320x240 for Banjo-Kazooie. 
        // If your recompilation outputs 640x480, update dimensions here.
        glTexSubImage2D(
            GL_TEXTURE_2D, 
            0,                  // Mipmap level
            0, 0,               // X/Y Offset
            320, 240,           // Width, Height
            GL_RGBA,            // Pixel format (RGBA8888)
            GL_UNSIGNED_BYTE,   // Data type
            alGlobals->screenBuffer // Pointer to actual pixel array
        );

        // 3. Unbind to prevent state leakage
        glBindTexture(GL_TEXTURE_2D, 0);
    }

} // extern "C"
