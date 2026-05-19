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

static int g_surfaceWidth = 320;
static int g_surfaceHeight = 240;

struct BKA_ControllerPad {
    uint16_t button;
    int8_t   stick_x;
    int8_t   stick_y;
    uint8_t  errno_val;
};

static BKA_ControllerPad g_inputMirror = {0, 0, 0, 0};
static pthread_mutex_t   g_inputMutex = PTHREAD_MUTEX_INITIALIZER;

static volatile bool g_vblankRequested = false;
static pthread_cond_t  g_vblankCond = PTHREAD_COND_INITIALIZER;
static pthread_mutex_t g_vblankMutex = PTHREAD_MUTEX_INITIALIZER;

extern "C" {
    extern uint8_t* gN64_RDRAM;
    extern uint32_t* gN64_Reg_Base;

    // Modified signature to pass asset path to memory allocator
    void InitN64Registers(const char* assetDir);
    void HardwareRegs_Shutdown(void);

    void BKA_StartEngine(void);
    void BKA_DropEngineLock(void);
    void BKA_ClaimEngineLock(void);

    void ResourceMgr_Init(const char* assetDir);

    extern BKA_ControllerPad gN64_ControllerData[4];
    void N64_TriggerVirtualVBlankInterrupt(void);

    void VideoPlugin_OutputFrameTexture(uint32_t hostTextureId);

    void BKA_FrameSyncHook(void) {
        pthread_mutex_lock(&g_vblankMutex);
        g_vblankRequested = true;

        BKA_DropEngineLock();

        while (g_vblankRequested) {
            pthread_cond_wait(&g_vblankCond, &g_vblankMutex);
        }

        BKA_ClaimEngineLock();
        pthread_mutex_unlock(&g_vblankMutex);
    }
}

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

    BKA_ClaimEngineLock();
    BKA_StartEngine();
    BKA_DropEngineLock();

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

    // CRITICAL CORRECTION: Pass the extraction path to the memory initializer
    InitN64Registers(g_otrPath.c_str());
    ResourceMgr_Init(g_otrPath.c_str());
    LOGI("NativeBridge: Resource Manager activated at: %s", g_otrPath.c_str());

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

JNIEXPORT void JNICALL 
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* env, jclass clazz, jint textureId) {
    if (gN64_RDRAM == nullptr || gN64_Reg_Base == nullptr) return;

    BKA_ClaimEngineLock();

    pthread_mutex_lock(&g_inputMutex);
    gN64_ControllerData[0] = g_inputMirror;
    pthread_mutex_unlock(&g_inputMutex);

    pthread_mutex_lock(&g_vblankMutex);
    if (g_vblankRequested) {
        N64_TriggerVirtualVBlankInterrupt();
        g_vblankRequested = false;
        pthread_cond_signal(&g_vblankCond);
    }
    pthread_mutex_unlock(&g_vblankMutex);

    VideoPlugin_OutputFrameTexture((uint32_t)textureId);

    BKA_DropEngineLock();
}

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
