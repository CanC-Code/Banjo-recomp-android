#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <string>
#include <cstdio>
#include <pthread.h>
#include <unistd.h>
#include <stdint.h>
#include <GLES2/gl2.h>

#define LOG_TAG "NativeBridge"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static JavaVM* g_jvm = nullptr;
static std::string g_otrPath;

// Layout constraints for display sizing
static int g_surfaceWidth = 320;
static int g_surfaceHeight = 240;

// Structured data map matching the original Ultra64 peripheral definitions
struct BKA_ControllerPad {
    uint16_t button;
    int8_t   stick_x;
    int8_t   stick_y;
    uint8_t  errno_val;
};

// Thread-safe controller data cache mirrors
static BKA_ControllerPad g_inputMirror = {0, 0, 0, 0};
static pthread_mutex_t   g_inputMutex = PTHREAD_MUTEX_INITIALIZER;

// Global flag tracking frame rendering sync states
static volatile bool g_vblankRequested = false;
static pthread_cond_t  g_vblankCond = PTHREAD_COND_INITIALIZER;
static pthread_mutex_t g_vblankMutex = PTHREAD_MUTEX_INITIALIZER;

extern "C" {
    extern uint8_t* gN64_RDRAM;
    extern uint32_t* gN64_Reg_Base;

    void InitN64Registers(void);
    void HardwareRegs_Shutdown(void);

    // Secure engine ignition entry point from emulator/stubs.cpp
    void BKA_StartEngine(void);
    
    // Core GIL scheduler lock context operators from emulator/stubs.cpp
    void BKA_DropEngineLock(void);
    void BKA_ClaimEngineLock(void);

    // High-Level Emulation Asset Interface
    void ResourceMgr_Init(const char* assetDir);

    // Core engine registration symbols located in the recompiled binary target
    extern BKA_ControllerPad gN64_ControllerData[4];
    void N64_TriggerVirtualVBlankInterrupt(void);

    // Modern hardware RDP hook provided by the recompiled rendering plugin wrapper
    void VideoPlugin_OutputFrameTexture(uint32_t hostTextureId);

    // Intercept loop inside the game cycle to regulate execution steps
    void BKA_FrameSyncHook(void) {
        pthread_mutex_lock(&g_vblankMutex);
        g_vblankRequested = true;

        // 1. RELEASE THE ENGINE LOCK before going to sleep.
        // This unblocks the background HLE PI Subsystem and Audio workers.
        BKA_DropEngineLock();

        // Block the recompiled game thread until the Android screen tick/render swap occurs
        while (g_vblankRequested) {
            pthread_cond_wait(&g_vblankCond, &g_vblankMutex);
        }

        // 2. RE-ACQUIRE THE ENGINE LOCK immediately upon waking up.
        // Guarantees this thread regains exclusive access to RDRAM memory mappings.
        BKA_ClaimEngineLock();

        pthread_mutex_unlock(&g_vblankMutex);
    }
}

// --- 1. Global JVM Capture Entry ---
JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved) {
    g_jvm = vm;
    LOGI("NativeBridge: JNI Link established securely.");
    return JNI_VERSION_1_6;
}

void* game_thread_fn(void* arg) {
    JNIEnv* env = nullptr;
    bool attached = false;

    if (g_jvm != nullptr) {
        if (g_jvm->AttachCurrentThread(&env, nullptr) == JNI_OK) {
            attached = true;
        }
    }

    // Launch core recompiled game engine inside the GIL safe-zone
    BKA_StartEngine();

    LOGI("NativeBridge: Core engine closed cleanly. Releasing runtime memory tables.");
    HardwareRegs_Shutdown();

    if (attached && g_jvm != nullptr) {
        g_jvm->DetachCurrentThread();
    }
    return nullptr;
}

extern "C" {

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass clazz, jobject context) {
    if (g_jvm == nullptr) env->GetJavaVM(&g_jvm);
}

JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPathStr, jobject assetManagerObj) {
    const char* otrPath = env->GetStringUTFChars(otrPathStr, nullptr);
    g_otrPath = otrPath;
    env->ReleaseStringUTFChars(otrPathStr, otrPath);

    InitN64Registers();
    ResourceMgr_Init(g_otrPath.c_str());
    LOGI("NativeBridge: Resource Manager activated in Self-Building mode at: %s", g_otrPath.c_str());

    pthread_t gameThread;
    if (pthread_create(&gameThread, nullptr, game_thread_fn, nullptr) == 0) {
        pthread_detach(gameThread);
        LOGI("NativeBridge: Standalone engine thread generated safely.");
    } else {
        LOGE("NativeBridge: Failed to create game thread.");
        HardwareRegs_Shutdown();
    }
}

JNIEXPORT void JNICALL 
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* env, jclass clazz, jint w, jint h) {
    g_surfaceWidth = w;
    g_surfaceHeight = h;
}

// --- 2. Graphics Interception Pass (Executed on the UI GL Thread) ---
JNIEXPORT void JNICALL 
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint textureId) {
    if (gN64_RDRAM == nullptr || gN64_Reg_Base == nullptr) return;

    // 1. CLAIM THE ENGINE LOCK. 
    // Freezes the game core instantly to eliminate multi-core data races during sync.
    BKA_ClaimEngineLock();

    // A: Thread-Safe Controller Mutation Pass under complete GIL coverage
    pthread_mutex_lock(&g_inputMutex);
    gN64_ControllerData[0] = g_inputMirror;
    pthread_mutex_unlock(&g_inputMutex);

    // B: Step Engine Clock Signal
    pthread_mutex_lock(&g_vblankMutex);
    if (g_vblankRequested) {
        // Assert register interrupt flags safely
        N64_TriggerVirtualVBlankInterrupt();
        g_vblankRequested = false;
        pthread_cond_signal(&g_vblankCond);
    }
    pthread_mutex_unlock(&g_vblankMutex);

    // C: Modern Native GPU Buffer Intercept
    // Guaranteed tear-free because the recompiled engine is stationary during read back.
    VideoPlugin_OutputFrameTexture((uint32_t)textureId);

    // 2. RELEASE THE ENGINE LOCK.
    // Unblocks the core game engine to resume executing instructions.
    BKA_DropEngineLock();
}

// --- 3. Input Conversion Bridge ---
JNIEXPORT void JNICALL 
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* env, jclass clazz, jint buttons, jfloat stickX, jfloat stickY) {
    pthread_mutex_lock(&g_inputMutex);

    g_inputMirror.button = (uint16_t)buttons;
    g_inputMirror.stick_x = (int8_t)(stickX * 80.0f);
    g_inputMirror.stick_y = (int8_t)(stickY * 80.0f);
    g_inputMirror.errno_val = 0;

    pthread_mutex_unlock(&g_inputMutex);
}

} // extern "C"
