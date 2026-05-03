#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static JavaVM* g_jvm         = nullptr;
static jobject   g_otrService  = nullptr;  
static jmethodID g_progressMid = nullptr;  

extern "C" {
    void ResourceMgr_Init(const char* otrPath, AAssetManager* assetMgr);
    void run_native_otr_generation_with_callback(JNIEnv* env, jobject callbackObj, jmethodID progressMid,
                                           int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                           const char* outDirPath);
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject otrService) {
    LOGI("nativeInit called");
    env->GetJavaVM(&g_jvm);

    if (g_otrService) {
        env->DeleteGlobalRef(g_otrService);
        g_otrService = nullptr;
    }
    g_otrService = env->NewGlobalRef(otrService);

    jclass svcClass = env->GetObjectClass(otrService);
    g_progressMid   = env->GetMethodID(svcClass, "updateOtrProgress", "(ILjava/lang/String;)V");
    if (!g_progressMid) {
        LOGE("nativeInit: could not find updateOtrProgress");
    }
    LOGI("nativeInit complete");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint fd, jobject assetManagerObj, jstring outDirStr) {
    LOGI("runOtrGeneration called, fd=%d", fd);
    const char* outDir = env->GetStringUTFChars(outDirStr, nullptr);
    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);

    AAsset* manifestAsset = AAssetManager_open(assetMgr, "manifest.bin", AASSET_MODE_BUFFER);
    if (manifestAsset) {
        uint8_t* manifestPtr = (uint8_t*)AAsset_getBuffer(manifestAsset);
        uint32_t manifestSize = AAsset_getLength(manifestAsset);
        
        run_native_otr_generation_with_callback(env, g_otrService, g_progressMid, fd, manifestPtr, manifestSize, outDir);
        
        AAsset_close(manifestAsset);
    } else {
        LOGE("runOtrGeneration: manifest.bin missing from assets folder!");
    }

    env->ReleaseStringUTFChars(outDirStr, outDir);
    LOGI("runOtrGeneration complete");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    LOGI("nativeGameBoot called");
    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);
    const char* otrPath  = env->GetStringUTFChars(otrPathStr, nullptr);

    ResourceMgr_Init(otrPath, assetMgr);   
    env->ReleaseStringUTFChars(otrPathStr, otrPath);

    LOGI("nativeGameBoot: GameLoop_run not yet implemented — stub returning");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint width, jint height) {
    LOGI("surfaceReady: %d x %d", width, height);
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint unused) {}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttonMask, jfloat stickX, jfloat stickY) {
    (void)buttonMask; (void)stickX; (void)stickY;
}

} // extern "C"
