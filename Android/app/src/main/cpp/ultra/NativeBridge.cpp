#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>
#include <vector>
#include <cstdio>
#include <pthread.h>
#include <unistd.h>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// --- Global JNI and State References ---
static JavaVM* g_jvm = nullptr;
static std::string g_otrPath;
static AAssetManager* g_assetMgr = nullptr;

// --- External Linkage to Recompiled Code and Resource Manager ---
extern "C" {
    void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize);
    
    /** * The entry point for the Banjo-Kazooie recompilation loop.
     * This must be called from a dedicated background thread.
     */
    void main_loop(); 

    /**
     * Defined in otr_builder.cpp
     */
    void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                               int romFd, const char* outDirPath, const char* manifestPath);
}

// --- Background Thread for the Game Loop ---
void* game_thread_fn(void* arg) {
    LOGI("Game Thread: Starting main_loop()");
    main_loop();
    return nullptr;
}

extern "C" {

/**
 * JNI exported method for OtrService.java
 * Matches the 'private native void runNativeOtrGeneration' signature.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_OtrService_runNativeOtrGeneration(JNIEnv* env, jobject instance, jobject callbackObj, 
                                                      jint romFd, jstring outDirStr, jstring manifestPathStr) {
    
    const char* outDir = env->GetStringUTFChars(outDirStr, nullptr);
    const char* manifestPath = env->GetStringUTFChars(manifestPathStr, nullptr);
    
    jclass svcClass = env->GetObjectClass(callbackObj);
    jmethodID progressMid = env->GetMethodID(svcClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    LOGI("NativeBridge: runNativeOtrGeneration triggered (fd: %d)", romFd);

    // Call the builder with manifest awareness
    run_native_otr_generation_with_callback(env, callbackObj, progressMid, romFd, outDir, manifestPath);

    env->ReleaseStringUTFChars(outDirStr, outDir);
    env->ReleaseStringUTFChars(manifestPathStr, manifestPath);
}

/**
 * Initializes the global JVM reference.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject context) {
    LOGI("NativeBridge: nativeInit called");
    env->GetJavaVM(&g_jvm);
}

/**
 * Starts the emulator. 
 * This replaces the "stub returning" logic with a dedicated pthread execution.
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    LOGI("NativeBridge: nativeGameBoot sequence starting...");

    const char* otrPath = env->GetStringUTFChars(otrPathStr, nullptr);
    g_assetMgr = AAssetManager_fromJava(env, assetManagerObj);
    g_otrPath = otrPath;

    // 1. Initialize the Resource Manager
    // Try US version first, then PAL
    std::string mPath = g_otrPath + "/manifest_us.bin";
    FILE* f = fopen(mPath.c_str(), "rb");
    if (!f) {
        mPath = g_otrPath + "/manifest_pal.bin";
        f = fopen(mPath.c_str(), "rb");
    }

    if (f) {
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        rewind(f);

        std::vector<uint8_t> buffer(size);
        fread(buffer.data(), 1, size, f);
        fclose(f);

        ResourceMgr_Init(otrPath, buffer.data(), (uint32_t)size);
        LOGI("NativeBridge: ResourceMgr ready with %ld byte manifest.", size);
    } else {
        LOGE("NativeBridge: CRITICAL - Manifest not found at %s", g_otrPath.c_str());
        env->ReleaseStringUTFChars(otrPathStr, otrPath);
        return; 
    }

    // 2. Launch the Game Thread
    // We spawn a pthread so the JNI call returns immediately, preventing a UI lock.
    pthread_t gameThread;
    if (pthread_create(&gameThread, nullptr, game_thread_fn, nullptr) != 0) {
        LOGE("NativeBridge: Failed to create game thread!");
    } else {
        pthread_detach(gameThread); // Allow the thread to run independently
        LOGI("NativeBridge: Game thread spawned successfully.");
    }

    env->ReleaseStringUTFChars(otrPathStr, otrPath);
}

/**
 * Stubs for surface and texture updates
 */
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint width, jint height) {
    LOGI("NativeBridge: surfaceReady (%d x %d)", width, height);
    // Notify your renderer of the new dimensions
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint unused) { }

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    // Implement input mapping here
}

} // extern "C"
