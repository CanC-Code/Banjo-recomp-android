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

// FIX 1: The manifest buffer must outlive nativeGameBoot's stack frame.
// The game thread calls ResourceMgr_HandleDma which reads g_assetDir (set from
// this buffer during ResourceMgr_Init). If this was a local std::vector it would
// be destroyed when nativeGameBoot returned, leaving the game thread writing into
// freed heap — the exact SEGV_ACCERR seen at fault addr 0x6ea21ca1c8.
// Promoting to static ensures the buffer lives for the process lifetime.
static std::vector<uint8_t> g_manifestBuf;

extern "C" {
    // The exact bootloader entry point defined in bk_boot_1050.c
    // C-linkage is required because bk_boot_1050.c is compiled as a standard C file.
    void func_80000450(int32_t arg0);

    void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize);
    
    // NOTE: run_native_otr_generation_with_callback declaration removed here 
    // as the JNI bridge is now entirely self-contained within otr_builder.cpp.
}

// Background thread loop to prevent UI lockup
void* game_thread_fn(void* arg) {
    LOGI("NativeBridge: Thread started. Launching game engine...");

    // Jump into the recompiled Banjo-Kazooie boot sequence.
    // 0 is passed as the default thread argument, matching native hardware behavior.
    func_80000450(0);

    LOGI("NativeBridge: Game engine returned cleanly.");
    return nullptr;
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject context) {
    env->GetJavaVM(&g_jvm);
    LOGI("NativeBridge: VM Reference captured.");
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    const char* otrPath = env->GetStringUTFChars(otrPathStr, nullptr);
    g_otrPath = otrPath;
    env->ReleaseStringUTFChars(otrPathStr, otrPath);

    // FIX 2: Dynamically detect which ROM version manifest exists.
    // Hardcoding "manifest_us.bin" will crash if the user extracted the PAL ROM.
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

    // FIX 3: Load the manifest into the static g_manifestBuf, not a local vector.
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

    // FIX 4: Use pthread_join instead of pthread_detach.
    //
    // pthread_detach caused nativeGameBoot to return immediately while the game
    // thread was still executing. The GL renderer then logged "nativeGameBoot
    // returned" and began teardown — freeing surfaces and GL state the game
    // thread was actively using. pthread_join blocks until func_80000450 exits,
    // so teardown only begins after the game has fully stopped.
    //
    // This is safe because nativeGameBoot is called from the GL thread's
    // dedicated BKA-GameThread (not the UI thread), so blocking here does not ANR.
    pthread_t gameThread;
    int rc = pthread_create(&gameThread, nullptr, game_thread_fn, nullptr);
    if (rc != 0) {
        LOGE("NativeBridge: pthread_create failed (errno %d). Aborting boot.", rc);
        g_manifestBuf.clear();
        return;
    }

    // Block the thread here until the game engine exits cleanly.
    pthread_join(gameThread, nullptr);
    LOGI("NativeBridge: Game thread joined. Boot sequence complete.");

    // Safe to release the manifest buffer now that the game thread has exited.
    g_manifestBuf.clear();
}

// Stubs for graphics/input pipeline. These must be filled with your actual 
// OpenGL ES rendering logic (e.g., eglSwapBuffers/glTexImage2D bridges) 
// for the game to display anything other than a black screen.
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint w, jint h) {}
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint u) {}
JNIEXPORT void JNICALL Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint b, jfloat x, jfloat y) {}

}
