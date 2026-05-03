#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>
#include <vector>
#include <cstdio>
#include <pthread.h>
#include <unistd.h>
#include <stdint.h>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static JavaVM* g_jvm = nullptr;
static std::string g_otrPath;

extern "C" {
    // The exact bootloader entry point defined in bk_boot_1050.c
    // C-linkage is required because bk_boot_1050.c is compiled as a standard C file.
    void func_80000450(int32_t arg0);
    
    void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize);
    void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                               int romFd, const char* outDirPath, const char* manifestPath);
}

// Background thread loop to prevent UI lockup
void* game_thread_fn(void* arg) {
    LOGI("NativeBridge: Thread started. Launching game engine...");
    
    // Jump into the recompiled Banjo-Kazooie boot sequence.
    // 0 is passed as the default thread argument, matching native hardware behavior.
    func_80000450(0); 
    
    return nullptr;
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_OtrService_runNativeOtrGeneration(JNIEnv* env, jobject instance, jobject callbackObj, 
                                                      jint romFd, jstring outDirStr, jstring manifestPathStr) {
    const char* outDir = env->GetStringUTFChars(outDirStr, nullptr);
    const char* manifestPath = env->GetStringUTFChars(manifestPathStr, nullptr);
    jclass svcClass = env->GetObjectClass(callbackObj);
    jmethodID progressMid = env->GetMethodID(svcClass, "onProgressUpdate", "(ILjava/lang/String;)V");

    run_native_otr_generation_with_callback(env, callbackObj, progressMid, romFd, outDir, manifestPath);

    env->ReleaseStringUTFChars(outDirStr, outDir);
    env->ReleaseStringUTFChars(manifestPathStr, manifestPath);
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject context) {
    env->GetJavaVM(&g_jvm);
    LOGI("NativeBridge: VM Reference captured.");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    const char* otrPath = env->GetStringUTFChars(otrPathStr, nullptr);
    g_otrPath = otrPath;

    // Attempt to load the manifest
    std::string mPath = g_otrPath + "/manifest_us.bin";
    FILE* f = fopen(mPath.c_str(), "rb");
    
    if (f) {
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        rewind(f);
        std::vector<uint8_t> buf(size);
        fread(buf.data(), 1, size, f);
        fclose(f);

        ResourceMgr_Init(otrPath, buf.data(), (uint32_t)size);
        LOGI("NativeBridge: Resource Manager active.");
        
        // SAFEGUARD: Launch Emulator Thread asynchronously ONLY if assets are valid
        pthread_t gameThread;
        pthread_create(&gameThread, nullptr, game_thread_fn, nullptr);
        pthread_detach(gameThread);
    } else {
        // ABORT: Prevent the engine from booting to avoid a fatal SIGSEGV
        LOGE("NativeBridge: Failed to load manifest at %s. Aborting boot sequence.", mPath.c_str());
    }

    env->ReleaseStringUTFChars(otrPathStr, otrPath);
}

JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint w, jint h) {}
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint u) {}
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint b, jfloat x, jfloat y) {}

}
