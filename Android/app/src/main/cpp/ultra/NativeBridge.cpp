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

// The manifest buffer must outlive nativeGameBoot's stack frame.
// Promoting to static ensures the buffer lives for the process lifetime,
// preventing SEGV_ACCERR when the DMA thread reads it.
static std::vector<uint8_t> g_manifestBuf;

extern "C" {
    // The exact bootloader entry point defined in bk_boot_1050.c
    void func_80000450(int32_t arg0);

    void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize);
}

// --- 1. Global JVM Capture ---
// Using JNI_OnLoad guarantees the JVM reference is captured the moment 
// System.loadLibrary() is called in Java, avoiding race conditions.
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved) {
    g_jvm = vm;
    LOGI("NativeBridge: JNI_OnLoad executed. JVM Reference captured.");
    return JNI_VERSION_1_6;
}

// --- 2. Thread Execution & JVM Attachment ---
// Background thread loop to prevent UI lockup
void* game_thread_fn(void* arg) {
    JNIEnv* env = nullptr;
    bool attached = false;

    // Attach this pure C++ thread to the Dalvik/ART JVM.
    // This is strictly required because internal game subsystems (like audio_bridge.cpp) 
    // will need to make JNI calls. Unattached threads cause instant crashes on JNI invocation.
    if (g_jvm != nullptr) {
        jint res = g_jvm->AttachCurrentThread(&env, nullptr);
        if (res == JNI_OK) {
            attached = true;
        } else {
            LOGE("NativeBridge: Failed to attach game thread to JVM (Error %d). Audio/Input callbacks may crash.", res);
        }
    }

    LOGI("NativeBridge: Thread started. Launching game engine...");

    // Jump into the recompiled Banjo-Kazooie boot sequence.
    func_80000450(0);

    LOGI("NativeBridge: Game engine returned cleanly.");

    // Detach thread to prevent memory leaks in the ART garbage collector
    if (attached && g_jvm != nullptr) {
        g_jvm->DetachCurrentThread();
    }

    return nullptr;
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject context) {
    // Left for backwards compatibility if called from Java, 
    // but g_jvm is already safely captured in JNI_OnLoad.
    if (g_jvm == nullptr) {
        env->GetJavaVM(&g_jvm);
    }
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    const char* otrPath = env->GetStringUTFChars(otrPathStr, nullptr);
    g_otrPath = otrPath;
    env->ReleaseStringUTFChars(otrPathStr, otrPath);

    // Dynamically detect which ROM version manifest exists.
    std::string mPathUs = g_otrPath + "/manifest_us.bin";
    std::string mPathPal = g_otrPath + "/manifest_pal.bin";
    std::string mPath = "";

    if (access(mPathUs.c_str(), F_OK) == 0) {
        mPath = mPathUs;
    } else if (access(mPathPal.c_str(), F_OK) == 0) {
        mPath = mPathPal;
    } else {
        LOGE("NativeBridge: Failed to find any manifest. Aborting boot.");
        return;
    }

    // Load the manifest into the static g_manifestBuf
    FILE* f = fopen(mPath.c_str(), "rb");
    if (!f) {
        LOGE("NativeBridge: Failed to open manifest at %s. Aborting boot.", mPath.c_str());
        return;
    }

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    rewind(f);

    if (size <= 0) {
        LOGE("NativeBridge: Manifest file is empty at %s. Aborting boot.", mPath.c_str());
        fclose(f);
        return;
    }

    g_manifestBuf.resize((size_t)size);
    size_t bytesRead = fread(g_manifestBuf.data(), 1, (size_t)size, f);
    fclose(f);

    if (bytesRead != (size_t)size) {
        LOGE("NativeBridge: Manifest read incomplete (%zu of %ld bytes). Aborting boot.", bytesRead, size);
        g_manifestBuf.clear();
        return;
    }

    ResourceMgr_Init(g_otrPath.c_str(), g_manifestBuf.data(), (uint32_t)size);
    LOGI("NativeBridge: Resource Manager active with manifest: %s", mPath.c_str());

    // Use pthread_join to synchronize engine shutdown with the Android lifecycle.
    // This blocks the Java background thread (BKA-GameThread) safely until the native
    // execution completes, preventing premature surface/buffer teardown.
    pthread_t gameThread;
    int rc = pthread_create(&gameThread, nullptr, game_thread_fn, nullptr);
    if (rc != 0) {
        LOGE("NativeBridge: pthread_create failed (errno %d). Aborting boot.", rc);
        g_manifestBuf.clear();
        return;
    }

    // Block the GL thread's executor wrapper until the native game engine exits.
    pthread_join(gameThread, nullptr);
    LOGI("NativeBridge: Game thread joined. Boot sequence complete.");

    // Safe to release the manifest buffer now that the game thread has fully detached and exited.
    g_manifestBuf.clear();
}

// Stubs for graphics/input pipeline. These must be populated with your actual 
// OpenGL ES rendering logic (e.g., eglSwapBuffers/glTexImage2D bridges) 
// for the game to display anything other than a black screen.
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint w, jint h) {}
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint u) {}
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint b, jfloat x, jfloat y) {}

}
