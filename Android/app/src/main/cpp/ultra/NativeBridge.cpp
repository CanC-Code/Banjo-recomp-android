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
static JavaVM*   g_jvm         = nullptr;
static jobject   g_otrService  = nullptr;  // global ref to OtrService instance
static jmethodID g_progressMid = nullptr;  // OtrService.updateOtrProgress(int, String)

// ============================================================
// Forward declarations for engine functions confirmed to exist
// in the compiled object files.
//
// ResourceMgr_Init — confirmed present in resource_mgr.cpp.o
//   (linker error: "did you mean: ResourceMgr_Init")
//
// OtrBuilder_run and GameLoop_run have no definition anywhere
// in the build; they are stubbed inline below until implemented.
// ============================================================
extern "C" {
    // Confirmed symbol from emulator/resource_mgr.cpp
    void ResourceMgr_Init(const char* otrPath, AAssetManager* assetMgr);
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
//    Caches the JavaVM, a global ref to the OtrService, and the
//    updateOtrProgress method ID so C++ threads can call back.
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
//    Runs asset extraction on the calling thread (OtrService's
//    BKA-ExtractionThread).
//
//    OtrBuilder_run has no definition in any compiled object —
//    stubbed here until otr_builder.cpp implements it.
//    Replace the stub body with the real call when ready:
//      OtrBuilder_run(static_cast<int>(fd), assetMgr, outDir);
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv*  env,
                                                  jclass   /*clazz*/,
                                                  jint     fd,
                                                  jobject  assetManagerObj,
                                                  jstring  outDirStr)
{
    LOGI("runOtrGeneration called, fd=%d", fd);

    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);
    const char*    outDir   = env->GetStringUTFChars(outDirStr, nullptr);

    // TODO: replace stub with OtrBuilder_run(fd, assetMgr, outDir)
    //       once ultra/otr_builder.cpp defines that symbol.
    LOGI("runOtrGeneration: OtrBuilder_run not yet implemented — stub returning");
    BKA_UpdateProgress(100, "done");

    env->ReleaseStringUTFChars(outDirStr, outDir);
    (void)assetMgr;
    // fd is now owned by C++; do not close here.
    LOGI("runOtrGeneration complete");
}

// ============================================================
// 3. nativeGameBoot(String otrPath, AssetManager assetManager)
//    Initialises ResourceMgr then enters the game loop (blocking).
//    Must be called on a dedicated background thread.
//
//    ResourceMgr_Init — confirmed symbol (capital I).
//    GameLoop_run     — no definition found anywhere in the build;
//                       stubbed here until implemented.
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env,
                                                jclass  /*clazz*/,
                                                jstring otrPathStr,
                                                jobject assetManagerObj)
{
    LOGI("nativeGameBoot called");

    AAssetManager* assetMgr = AAssetManager_fromJava(env, assetManagerObj);
    const char*    otrPath  = env->GetStringUTFChars(otrPathStr, nullptr);

    ResourceMgr_Init(otrPath, assetMgr);   // confirmed symbol — capital I
    env->ReleaseStringUTFChars(otrPathStr, otrPath);

    // TODO: replace stub with real game loop entry point once
    //       that symbol exists in the build.
    LOGI("nativeGameBoot: GameLoop_run not yet implemented — stub returning");
}

// ============================================================
// 4. surfaceReady(int width, int height)
//    Called from the GL thread inside onSurfaceCreated.
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* /*env*/,
                                              jclass  /*clazz*/,
                                              jint    width,
                                              jint    height)
{
    LOGI("surfaceReady: %d x %d", width, height);
    // TODO: allocate / resize the framebuffer texture here.
}

// ============================================================
// 5. updateTexture(int unused)
//    Called every frame from the GL thread.
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* /*env*/,
                                               jclass  /*clazz*/,
                                               jint    /*unused*/)
{
    // TODO: blit N64 framebuffer → GL texture and draw fullscreen quad.
}

// ============================================================
// 6. nativeUpdateInput(int buttonMask, float stickX, float stickY)
//    Pushes controller state into the N64 input layer.
// ============================================================
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* /*env*/,
                                                   jclass  /*clazz*/,
                                                   jint    buttonMask,
                                                   jfloat  stickX,
                                                   jfloat  stickY)
{
    // TODO: forward to N64 controller emulation layer.
    (void)buttonMask; (void)stickX; (void)stickY;
}

} // extern "C"
