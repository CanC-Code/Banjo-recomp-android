#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <GLES3/gl3.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

#include "n64_types.h"

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  TAG, __VA_ARGS__)

// -----------------------------------------------------------------------
// External symbols
// -----------------------------------------------------------------------
extern "C" {
    extern AndroidBridgeGlobals* gBridgeGlobals;

    // From exceptasm.cpp
    extern void initInterruptTables();

    // From resource_mgr.cpp
    extern void ResourceMgr_Init(const char* assetDir,
                                 uint8_t*    manifestBuf,
                                 uint32_t    manifestSize);

    // From otr_builder.cpp
    extern void run_native_otr_generation_with_callback(
        JNIEnv* env, jobject callbackObj, jmethodID progressMid,
        int romFd, uint8_t* manifestPtr, uint32_t manifestSize,
        const char* outDirPath);

    // From stubs.cpp — the real game loop driver
    extern void mainLoop();
}

// -----------------------------------------------------------------------
// Module-level state
// -----------------------------------------------------------------------
static jobject    g_service_ref   = nullptr;
static jmethodID  g_progress_mid  = nullptr;

// GL texture that we write the N64 framebuffer into each frame
static GLuint     g_fb_texture    = 0;

// Flag so the game loop thread knows the GL surface is ready
static volatile bool g_surface_ready = false;

// -----------------------------------------------------------------------
// nativeInit – called from Java before runOtrGeneration
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass /*clazz*/, jobject serviceObj) {
    if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
    g_service_ref = env->NewGlobalRef(serviceObj);

    jclass serviceClass = env->GetObjectClass(g_service_ref);
    g_progress_mid = env->GetMethodID(serviceClass,
                                      "updateOtrProgress",
                                      "(ILjava/lang/String;)V");
    LOGI("nativeInit: JNI bridge ready");
}

// -----------------------------------------------------------------------
// runOtrGeneration – extracts ROM assets into getFilesDir()
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv*  env,
                                                   jclass   /*clazz*/,
                                                   jint     romFd,
                                                   jobject  assetManager,
                                                   jstring  outDir) {
    const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
    AAssetManager* nativeMgr = AAssetManager_fromJava(env, assetManager);

    AAsset* asset = AAssetManager_open(nativeMgr, "manifest_us.bin",
                                       AASSET_MODE_BUFFER);
    if (asset == nullptr) {
        LOGE("runOtrGeneration: manifest_us.bin not found in APK assets!");
        env->ReleaseStringUTFChars(outDir, nativeOutDir);
        return;
    }

    uint8_t* manifestBuf  = (uint8_t*)AAsset_getBuffer(asset);
    uint32_t manifestSize = (uint32_t)AAsset_getLength(asset);

    run_native_otr_generation_with_callback(env, g_service_ref, g_progress_mid,
                                            (int)romFd, manifestBuf, manifestSize,
                                            nativeOutDir);
    AAsset_close(asset);
    env->ReleaseStringUTFChars(outDir, nativeOutDir);
}

// -----------------------------------------------------------------------
// nativeGameBoot
//
// Called from the Java background thread after extraction is confirmed.
// Steps:
//   1. Allocate AndroidBridgeGlobals (screenBuffer = 320×240 RGBA8)
//   2. Init interrupt tables
//   3. Load the manifest and init ResourceMgr with the asset directory
//   4. Start the game loop (blocking — runs for the lifetime of the session)
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env,
                                                 jclass  /*clazz*/,
                                                 jstring otrPathJ,
                                                 jobject assetManager) {
    // --- 1. Allocate bridge globals and framebuffer ---
    if (gBridgeGlobals == nullptr) {
        void* ptr = nullptr;
        if (posix_memalign(&ptr, 16, sizeof(AndroidBridgeGlobals)) != 0) {
            LOGE("nativeGameBoot: failed to allocate AndroidBridgeGlobals");
            return;
        }
        memset(ptr, 0, sizeof(AndroidBridgeGlobals));
        gBridgeGlobals = (AndroidBridgeGlobals*)ptr;
    }

    // N64 framebuffer: 320×240, 4 bytes per pixel (RGBA8)
    if (gBridgeGlobals->screenBuffer == nullptr) {
        gBridgeGlobals->screenBuffer =
            (uint32_t*)malloc(320 * 240 * sizeof(uint32_t));
        if (!gBridgeGlobals->screenBuffer) {
            LOGE("nativeGameBoot: failed to allocate screenBuffer");
            return;
        }
        memset(gBridgeGlobals->screenBuffer, 0,
               320 * 240 * sizeof(uint32_t));
    }

    // --- 2. Init interrupt / exception tables ---
    initInterruptTables();
    LOGI("nativeGameBoot: interrupt tables initialised");

    // --- 3. Init ResourceMgr with the asset directory and manifest ---
    const char* assetDir = env->GetStringUTFChars(otrPathJ, nullptr);

    AAssetManager* nativeMgr = AAssetManager_fromJava(env, assetManager);
    AAsset* manifestAsset = AAssetManager_open(nativeMgr, "manifest_us.bin",
                                               AASSET_MODE_BUFFER);
    if (manifestAsset != nullptr) {
        uint8_t* manifestBuf  = (uint8_t*)AAsset_getBuffer(manifestAsset);
        uint32_t manifestSize = (uint32_t)AAsset_getLength(manifestAsset);

        ResourceMgr_Init(assetDir, manifestBuf, manifestSize);
        AAsset_close(manifestAsset);
        LOGI("nativeGameBoot: ResourceMgr initialised with dir='%s'", assetDir);
    } else {
        LOGE("nativeGameBoot: manifest_us.bin missing — DMA will zero-fill!");
        // Still call Init so the dir is set; DMA will warn-and-zero-fill
        ResourceMgr_Init(assetDir, nullptr, 0);
    }

    env->ReleaseStringUTFChars(otrPathJ, assetDir);

    // --- 4. Enter the game loop (this call does not return) ---
    LOGI("nativeGameBoot: entering mainLoop");
    mainLoop();

    LOGW("nativeGameBoot: mainLoop returned unexpectedly");
}

// -----------------------------------------------------------------------
// surfaceReady – called from GLRenderer.onSurfaceCreated
// Signals that the GL context exists and we can upload textures.
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* /*env*/, jclass /*clazz*/,
                                               jint width, jint height) {
    // Allocate the fullscreen framebuffer texture once
    if (g_fb_texture == 0) {
        glGenTextures(1, &g_fb_texture);
        glBindTexture(GL_TEXTURE_2D, g_fb_texture);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        // Allocate storage: 320×240 RGBA8
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 320, 240, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glBindTexture(GL_TEXTURE_2D, 0);
        LOGI("surfaceReady: framebuffer texture allocated (id=%u)", g_fb_texture);
    }
    g_surface_ready = true;
    (void)width; (void)height;
}

// -----------------------------------------------------------------------
// updateTexture – called every frame from GLRenderer.onDrawFrame
//
// Uploads the N64 RGBA8 framebuffer to the GL texture, then draws a
// fullscreen quad so the texture fills the entire display.
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* /*env*/, jclass /*clazz*/,
                                                jint /*unused*/) {
    if (!g_surface_ready || g_fb_texture == 0) return;
    if (gBridgeGlobals == nullptr || gBridgeGlobals->screenBuffer == nullptr) return;

    // --- Upload framebuffer ---
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glTexSubImage2D(GL_TEXTURE_2D, 0,
                    0, 0, 320, 240,
                    GL_RGBA, GL_UNSIGNED_BYTE,
                    gBridgeGlobals->screenBuffer);
    glBindTexture(GL_TEXTURE_2D, 0);

    // --- Draw fullscreen quad using fixed-function GLES2 path ---
    // Vertex positions (NDC) and UV coordinates for a fullscreen quad
    static const float kQuadVerts[] = {
    //  X      Y     U     V
       -1.0f, -1.0f, 0.0f, 1.0f,   // bottom-left  (UV flipped Y for GL)
        1.0f, -1.0f, 1.0f, 1.0f,   // bottom-right
       -1.0f,  1.0f, 0.0f, 0.0f,   // top-left
        1.0f,  1.0f, 1.0f, 0.0f,   // top-right
    };

    // Minimal inline GLSL shader — compiled once, cached in static locals
    static GLuint s_prog = 0;
    if (s_prog == 0) {
        const char* vsrc =
            "attribute vec2 aPos;\n"
            "attribute vec2 aUV;\n"
            "varying vec2 vUV;\n"
            "void main() { gl_Position = vec4(aPos,0,1); vUV = aUV; }\n";
        const char* fsrc =
            "precision mediump float;\n"
            "varying vec2 vUV;\n"
            "uniform sampler2D uTex;\n"
            "void main() { gl_FragColor = texture2D(uTex,vUV); }\n";

        auto compile = [](GLenum type, const char* src) -> GLuint {
            GLuint s = glCreateShader(type);
            glShaderSource(s, 1, &src, nullptr);
            glCompileShader(s);
            return s;
        };

        GLuint vs = compile(GL_VERTEX_SHADER,   vsrc);
        GLuint fs = compile(GL_FRAGMENT_SHADER, fsrc);
        s_prog = glCreateProgram();
        glAttachShader(s_prog, vs);
        glAttachShader(s_prog, fs);
        glBindAttribLocation(s_prog, 0, "aPos");
        glBindAttribLocation(s_prog, 1, "aUV");
        glLinkProgram(s_prog);
        glDeleteShader(vs);
        glDeleteShader(fs);
        LOGI("updateTexture: fullscreen quad shader compiled (prog=%u)", s_prog);
    }

    glClear(GL_COLOR_BUFFER_BIT);
    glUseProgram(s_prog);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glUniform1i(glGetUniformLocation(s_prog, "uTex"), 0);

    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), kQuadVerts);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float), kQuadVerts + 2);
    glEnableVertexAttribArray(0);
    glEnableVertexAttribArray(1);

    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);

    glDisableVertexAttribArray(0);
    glDisableVertexAttribArray(1);
    glBindTexture(GL_TEXTURE_2D, 0);
    glUseProgram(0);
}

// -----------------------------------------------------------------------
// nativeUpdateInput
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv* /*env*/, jclass /*clazz*/,
                                                    jint    buttonMask,
                                                    jfloat  stickX,
                                                    jfloat  stickY) {
    // TODO: feed into the N64 controller emulation layer
    (void)buttonMask; (void)stickX; (void)stickY;
}
