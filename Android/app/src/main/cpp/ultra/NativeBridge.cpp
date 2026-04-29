#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <GLES3/gl3.h> // Added for OpenGL functions
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>
#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

// We wrap everything in a single extern "C" block to be safe and clean
extern "C" {
    // Engine globals and external functions
    extern ALGlobals* alGlobals;
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);
    
    // Placeholder for the engine's frame processing function
    // Replace this with your actual engine tick function (e.g., Banjo_Step() )
    extern void game_engine_update(); 

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

    // THIS IS THE REAL GAME LOOP!
    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint textureId) {
        if (alGlobals == nullptr) return;

        // 1. Tell the engine to calculate the next frame
        // game_engine_update(); 

        // 2. Bind the texture created by the Java GLRenderer
        glBindTexture(GL_TEXTURE_2D, textureId);

        // 3. Upload the engine's framebuffer to the GPU texture
        // Note: Change 320/240 and alGlobals->framebuffer to match your engine's actual output
        if (alGlobals != nullptr) {
            glTexSubImage2D(
                GL_TEXTURE_2D, 
                0,              // Level
                0, 0,           // Offset
                320, 240,       // Resolution (Standard N64)
                GL_RGBA,        // Format
                GL_UNSIGNED_BYTE, 
                alGlobals;      // Pointer to raw pixel data
            );
        }

        // 4. Unbind
        glBindTexture(GL_TEXTURE_2D, 0);
    }
} // End of extern "C"
