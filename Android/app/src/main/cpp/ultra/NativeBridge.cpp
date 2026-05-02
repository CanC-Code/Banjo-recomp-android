// app/src/main/cpp/NativeBridge.cpp

// File: Android/app/src/main/cpp/ultra/NativeBridge.cpp
//
// JNI entrypoints for com.bkawrapper.NativeBridge.
// Every method declared `native` in NativeBridge.java must have a matching
// symbol here, or the JVM will throw UnsatisfiedLinkError at runtime.
//
// Signature rules (all methods are `static native` in Java):
//   static native  →  (JNIEnv*, jclass,  <args...>)
//   instance native →  (JNIEnv*, jobject, <args...>)
// All six methods in NativeBridge.java are static, so jclass is correct.

#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>
#include <unistd.h>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ============================================================
// Internal state — set by nativeInit, used by runOtrGeneration
// and updateOtrProgress callbacks.
// ============================================================
static JavaVM* g_jvm         = nullptr;
static jobject   g_otrService  = nullptr;  // global ref to OtrService instance
static jmethodID g_progressMid = nullptr;  // OtrService.updateOtrProgress(int, String)

// ============================================================
// Forward declarations for engine functions confirmed to exist
// in the compiled object files.
// ============================================================
extern "C" {
    void ResourceMgr_Init(const char* otrPath, AAssetManager* assetMgr);
    void OtrBuilder_run(int fd, AAssetManager* assetMgr, const char* outDir);
}

// ============================================================
// Helper — call OtrService.updateOtrProgress(int, String) from
// any thread (including C++ worker threads).
// ============================================================
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
        env->CallVoidMethod(g_otrService, g_progressMid,
                            static_cast<jint>(percent), jStatus);
        env->DeleteLocalRef(jStatus);
        if (env->ExceptionCheck()) env->ExceptionClear();
    }

    if (attached) g_jvm->DetachCurrentThread();
}

extern "C" {

// ============================================================
// 1. nativeInit(OtrService service)
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env,
                                            jclass  /*clazz*/,
                                            jobject  otrService)
{
    LOGI("nativeInit called");

    env->GetJavaVM(&g_jvm);

    if (g_otrService) {
        env->DeleteGlobalRef(g_otrService);
        g_otrService = nullptr;
    }
    g_otrService = env->NewGlobalRef(otrService);

    jclass svcClass = env->GetObjectClass(otrService);
    g_progressMid   = env->GetMethodID(svcClass,
                                       "updateOtrProgress",
                                       "(ILjava/lang/String;)V");
    if (!g_progressMid) {
        LOGE("nativeInit: could not find updateOtrProgress — progress callbacks will be silent");
    }

    LOGI("nativeInit complete");
}

// ============================================================
// 2. runOtrGeneration(int fd, AssetManager assetManager, String outDir)
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env,
                                                  jclass   /*clazz*/,
                                                  jint     fd,
                                                  jobject  assetManagerObj,
                                                  jstring  outDirStr)
{
    LOGI("runOtrGeneration called, fd=%d", fd);

    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);
    const char* outDir   = env->GetStringUTFChars(outDirStr, nullptr);

    // Call the actual implemented builder logic
    OtrBuilder_run(static_cast<int>(fd), assetMgr, outDir);

    env->ReleaseStringUTFChars(outDirStr, outDir);
    (void)assetMgr;
    LOGI("runOtrGeneration complete");
}

// ============================================================
// 3. nativeGameBoot(String otrPath, AssetManager assetManager)
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env,
                                                jclass  /*clazz*/,
                                                jstring otrPathStr,
                                                jobject assetManagerObj)
{
    LOGI("nativeGameBoot called");

    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);
    const char* otrPath  = env->GetStringUTFChars(otrPathStr, nullptr);

    ResourceMgr_Init(otrPath, assetMgr);   
    env->ReleaseStringUTFChars(otrPathStr, otrPath);

    LOGI("nativeGameBoot: GameLoop_run not yet implemented — stub returning");
}

// ============================================================
// 4. surfaceReady(int width, int height)
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* /*env*/,
                                              jclass  /*clazz*/,
                                              jint    width,
                                              jint    height)
{
    LOGI("surfaceReady: %d x %d", width, height);
}

// ============================================================
// 5. updateTexture(int unused)
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* /*env*/,
                                               jclass  /*clazz*/,
                                               jint    /*unused*/)
{
}

// ============================================================
// 6. nativeUpdateInput(int buttonMask, float stickX, float stickY)
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* /*env*/,
                                                   jclass  /*clazz*/,
                                                   jint    buttonMask,
                                                   jfloat  stickX,
                                                   jfloat  stickY)
{
    (void)buttonMask; (void)stickX; (void)stickY;
}

} // extern "C"
