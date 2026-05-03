#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>
#include <unistd.h>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static JavaVM* g_jvm         = nullptr;
static jobject   g_otrService  = nullptr;  
static jmethodID g_progressMid = nullptr;  

extern "C" {
    void ResourceMgr_Init(const char* otrPath, AAssetManager* assetMgr);
    bool OtrBuilder_run(int fd, const char* outDir); 
}

extern "C" void BKA_UpdateProgress(int percent, const char* status) {
    if (!g_jvm || !g_otrService || !g_progressMid) return;

    JNIEnv* env     = nullptr;
    bool    attached = false;

    jint rc = g_jvm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6);
    if (rc == JNI_EDETACHED) {
        g_jvm->AttachCurrentThread(&env, nullptr);
        attached = true;
    }

    if (env) {
        jstring jStatus = env->NewStringUTF(status ? status : "");
        env->CallVoidMethod(g_otrService, g_progressMid, static_cast<jint>(percent), jStatus);
        env->DeleteLocalRef(jStatus);
        if (env->ExceptionCheck()) env->ExceptionClear();
    }

    if (attached) g_jvm->DetachCurrentThread();
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

JNIEXPORT jboolean JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass clazz, jint fd, jstring outDirStr) {
    LOGI("runOtrGeneration called, fd=%d", fd);
    const char* outDir = env->GetStringUTFChars(outDirStr, nullptr);

    bool success = OtrBuilder_run(static_cast<int>(fd), outDir);

    env->ReleaseStringUTFChars(outDirStr, outDir);
    LOGI("runOtrGeneration complete: Success=%d", success);
    return success ? JNI_TRUE : JNI_FALSE;
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
