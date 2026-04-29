#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <GLES3/gl3.h>
#include <stdint.h>
#include <stdlib.h> 
#include <string.h>

#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

extern "C" {
    // Linked to the renamed struct
    extern AndroidBridgeGlobals* gBridgeGlobals; 
    
    extern void initInterruptTables();
    extern void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                                        int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                                        const char* outDirPath);

    static jobject g_service_ref = nullptr;
    static jmethodID g_progress_mid = nullptr;

    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject serviceObj) {
        if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
        g_service_ref = env->NewGlobalRef(serviceObj);

        jclass serviceClass = env->GetObjectClass(g_service_ref);
        g_progress_mid = env->GetMethodID(serviceClass, "updateOtrProgress", "(ILjava/lang/String;)V");
        LOGI("NativeBridge Initialized.");
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
        if (gBridgeGlobals == nullptr) {
            void* ptr = nullptr;
            if (posix_memalign(&ptr, 16, sizeof(AndroidBridgeGlobals)) == 0) {
                memset(ptr, 0, sizeof(AndroidBridgeGlobals));
                gBridgeGlobals = (AndroidBridgeGlobals*)ptr;
            }
        }

        initInterruptTables();
        LOGI("Engine Memory Booted!");
    }

    JNIEXPORT void JNICALL
    Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint textureId) {
        if (gBridgeGlobals == nullptr || gBridgeGlobals->screenBuffer == nullptr) return;

        glBindTexture(GL_TEXTURE_2D, textureId);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 320, 240, GL_RGBA, GL_UNSIGNED_BYTE, gBridgeGlobals->screenBuffer);
        glBindTexture(GL_TEXTURE_2D, 0);
    }
}
