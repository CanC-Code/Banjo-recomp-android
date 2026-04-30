#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <GLES3/gl3.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <stdatomic.h>   // atomic_bool, atomic_store, atomic_load

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
    extern void initInterruptTables();
    extern void ResourceMgr_Init(const char* assetDir,
                                 uint8_t*    manifestBuf,
                                 uint32_t    manifestSize);
    extern void run_native_otr_generation_with_callback(
        JNIEnv* env, jobject callbackObj, jmethodID progressMid,
        int romFd, uint8_t* manifestPtr, uint32_t manifestSize,
        const char* outDirPath);
    extern void mainLoop();
}

// -----------------------------------------------------------------------
// Module-level state
// -----------------------------------------------------------------------
static jobject   g_service_ref  = nullptr;
static jmethodID g_progress_mid = nullptr;

static GLuint        g_fb_texture   = 0;
static GLuint        g_quad_prog    = 0;

// Atomic flags — written from game thread, read from GL thread (and vice versa).
// Using C11 stdatomic so both C and C++ translation units can share them.
static atomic_bool g_surface_ready  = ATOMIC_VAR_INIT(0);
static atomic_bool g_globals_ready  = ATOMIC_VAR_INIT(0);

// -----------------------------------------------------------------------
// Internal helpers
// -----------------------------------------------------------------------

/** Allocates gBridgeGlobals and its screenBuffer exactly once. */
static void ensureBridgeGlobals() {
    if (gBridgeGlobals == nullptr) {
        void* ptr = nullptr;
        if (posix_memalign(&ptr, 16, sizeof(AndroidBridgeGlobals)) != 0) {
            LOGE("ensureBridgeGlobals: posix_memalign failed");
            return;
        }
        memset(ptr, 0, sizeof(AndroidBridgeGlobals));
        gBridgeGlobals = (AndroidBridgeGlobals*)ptr;
    }

    if (gBridgeGlobals->screenBuffer == nullptr) {
        gBridgeGlobals->screenBuffer =
            (uint32_t*)malloc(320u * 240u * sizeof(uint32_t));
        if (!gBridgeGlobals->screenBuffer) {
            LOGE("ensureBridgeGlobals: screenBuffer malloc failed");
            return;
        }
        // Fill with a visible colour on first frame so we can confirm
        // rendering is working even before the game writes anything.
        // 0xFF0000FF = opaque red in RGBA8 — easy to spot vs black.
        uint32_t* buf = gBridgeGlobals->screenBuffer;
        for (int i = 0; i < 320 * 240; i++) buf[i] = 0xFF0000FFu;
    }

    atomic_store(&g_globals_ready, 1);
    LOGI("ensureBridgeGlobals: ready (screenBuffer=%p)", gBridgeGlobals->screenBuffer);
}

/** Compile one GLSL shader stage. Returns 0 on failure. */
static GLuint compileShader(GLenum type, const char* src) {
    GLuint s = glCreateShader(type);
    glShaderSource(s, 1, &src, nullptr);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char buf[512];
        glGetShaderInfoLog(s, sizeof(buf), nullptr, buf);
        LOGE("Shader compile error: %s", buf);
        glDeleteShader(s);
        return 0;
    }
    return s;
}

/** Build the fullscreen-quad shader program exactly once on the GL thread. */
static GLuint buildQuadProgram() {
    const char* vsrc =
        "#version 300 es\n"
        "in vec2 aPos;\n"
        "in vec2 aUV;\n"
        "out vec2 vUV;\n"
        "void main() { gl_Position = vec4(aPos, 0.0, 1.0); vUV = aUV; }\n";

    const char* fsrc =
        "#version 300 es\n"
        "precision mediump float;\n"
        "in vec2 vUV;\n"
        "uniform sampler2D uTex;\n"
        "out vec4 fragColor;\n"
        "void main() { fragColor = texture(uTex, vUV); }\n";

    GLuint vs = compileShader(GL_VERTEX_SHADER,   vsrc);
    GLuint fs = compileShader(GL_FRAGMENT_SHADER, fsrc);
    if (!vs || !fs) { glDeleteShader(vs); glDeleteShader(fs); return 0; }

    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs);
    glAttachShader(prog, fs);
    glBindAttribLocation(prog, 0, "aPos");
    glBindAttribLocation(prog, 1, "aUV");
    glLinkProgram(prog);

    GLint ok = 0;
    glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    if (!ok) {
        char buf[512];
        glGetProgramInfoLog(prog, sizeof(buf), nullptr, buf);
        LOGE("Program link error: %s", buf);
        glDeleteProgram(prog);
        prog = 0;
    }
    glDeleteShader(vs);
    glDeleteShader(fs);
    return prog;
}

// -----------------------------------------------------------------------
// nativeInit
// Called from Java BEFORE runOtrGeneration.
// We allocate gBridgeGlobals here so it is guaranteed to exist before the
// GL thread calls surfaceReady.
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass /*clazz*/,
                                             jobject serviceObj) {
    if (g_service_ref != nullptr) env->DeleteGlobalRef(g_service_ref);
    g_service_ref = env->NewGlobalRef(serviceObj);

    jclass cls = env->GetObjectClass(g_service_ref);
    g_progress_mid = env->GetMethodID(cls, "updateOtrProgress",
                                      "(ILjava/lang/String;)V");

    // Allocate bridge globals early so the GL thread never races against
    // nativeGameBoot for the gBridgeGlobals pointer.
    ensureBridgeGlobals();

    LOGI("nativeInit: JNI bridge ready, globals allocated");
}

// -----------------------------------------------------------------------
// runOtrGeneration
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv*  env,
                                                   jclass   /*clazz*/,
                                                   jint     romFd,
                                                   jobject  assetManager,
                                                   jstring  outDir) {
    const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
    AAssetManager* mgr = AAssetManager_fromJava(env, assetManager);

    AAsset* asset = AAssetManager_open(mgr, "manifest_us.bin",
                                       AASSET_MODE_BUFFER);
    if (asset == nullptr) {
        LOGE("runOtrGeneration: manifest_us.bin not found in APK assets");
        env->ReleaseStringUTFChars(outDir, nativeOutDir);
        return;
    }

    uint8_t* buf  = (uint8_t*)AAsset_getBuffer(asset);
    uint32_t size = (uint32_t)AAsset_getLength(asset);

    run_native_otr_generation_with_callback(
        env, g_service_ref, g_progress_mid,
        (int)romFd, buf, size, nativeOutDir);

    AAsset_close(asset);
    env->ReleaseStringUTFChars(outDir, nativeOutDir);
}

// -----------------------------------------------------------------------
// nativeGameBoot
// Called on a dedicated background thread from MainActivity.bootGameEngine().
// Initialises the engine then enters mainLoop (does not return).
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env,
                                                 jclass  /*clazz*/,
                                                 jstring otrPathJ,
                                                 jobject assetManager) {
    // Ensure globals exist (nativeInit should have done this already,
    // but guard in case bootGameEngine is called on a fresh-install path
    // where nativeInit was not called).
    ensureBridgeGlobals();

    initInterruptTables();
    LOGI("nativeGameBoot: interrupt tables initialised");

    const char* assetDir = env->GetStringUTFChars(otrPathJ, nullptr);
    AAssetManager* mgr = AAssetManager_fromJava(env, assetManager);

    AAsset* manifestAsset = AAssetManager_open(mgr, "manifest_us.bin",
                                               AASSET_MODE_BUFFER);
    if (manifestAsset != nullptr) {
        uint8_t* buf  = (uint8_t*)AAsset_getBuffer(manifestAsset);
        uint32_t size = (uint32_t)AAsset_getLength(manifestAsset);
        ResourceMgr_Init(assetDir, buf, size);
        AAsset_close(manifestAsset);
        LOGI("nativeGameBoot: ResourceMgr initialised, dir='%s'", assetDir);
    } else {
        LOGE("nativeGameBoot: manifest_us.bin missing — DMA will zero-fill");
        ResourceMgr_Init(assetDir, nullptr, 0);
    }

    env->ReleaseStringUTFChars(otrPathJ, assetDir);

    LOGI("nativeGameBoot: entering mainLoop");
    mainLoop();
    LOGW("nativeGameBoot: mainLoop returned");
}

// -----------------------------------------------------------------------
// surfaceReady
// Called from GLRenderer.onSurfaceCreated on the GL thread.
// Allocates the framebuffer texture and builds the quad shader.
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv* /*env*/, jclass /*clazz*/,
                                               jint width, jint height) {
    LOGI("surfaceReady: %d x %d", width, height);

    // Build quad shader program
    if (g_quad_prog == 0) {
        g_quad_prog = buildQuadProgram();
        if (g_quad_prog == 0) {
            LOGE("surfaceReady: shader compilation failed");
            return;
        }
        LOGI("surfaceReady: quad shader ready (prog=%u)", g_quad_prog);
    }

    // Allocate / re-allocate the framebuffer texture
    if (g_fb_texture != 0) {
        glDeleteTextures(1, &g_fb_texture);
        g_fb_texture = 0;
    }
    glGenTextures(1, &g_fb_texture);
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    // If globals are ready, upload the initial red frame immediately so we
    // get a visible colour on the very first draw call.
    void* initialData = nullptr;
    if (atomic_load(&g_globals_ready) && gBridgeGlobals != nullptr) {
        initialData = gBridgeGlobals->screenBuffer;
    }
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 320, 240, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, initialData);
    glBindTexture(GL_TEXTURE_2D, 0);

    LOGI("surfaceReady: texture allocated (id=%u)", g_fb_texture);
    atomic_store(&g_surface_ready, 1);
}

// -----------------------------------------------------------------------
// updateTexture
// Called every frame from GLRenderer.onDrawFrame on the GL thread.
// Uploads screenBuffer and draws it as a fullscreen quad.
// -----------------------------------------------------------------------
extern "C"
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv* /*env*/, jclass /*clazz*/,
                                                jint /*unused*/) {
    if (!atomic_load(&g_surface_ready))  return;
    if (!atomic_load(&g_globals_ready))  return;
    if (g_fb_texture == 0)               return;
    if (g_quad_prog  == 0)               return;
    if (gBridgeGlobals == nullptr)       return;
    if (gBridgeGlobals->screenBuffer == nullptr) return;

    // Upload current N64 framebuffer
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glTexSubImage2D(GL_TEXTURE_2D, 0,
                    0, 0, 320, 240,
                    GL_RGBA, GL_UNSIGNED_BYTE,
                    gBridgeGlobals->screenBuffer);
    glBindTexture(GL_TEXTURE_2D, 0);

    // Draw fullscreen quad
    // Positions (NDC) + UVs — UV Y is flipped for GL convention
    static const float kVerts[] = {
    //   X      Y     U     V
       -1.0f, -1.0f, 0.0f, 1.0f,
        1.0f, -1.0f, 1.0f, 1.0f,
       -1.0f,  1.0f, 0.0f, 0.0f,
        1.0f,  1.0f, 1.0f, 0.0f,
    };

    glClear(GL_COLOR_BUFFER_BIT);
    glUseProgram(g_quad_prog);

    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glUniform1i(glGetUniformLocation(g_quad_prog, "uTex"), 0);

    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE,
                          4 * sizeof(float), kVerts);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE,
                          4 * sizeof(float), kVerts + 2);
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
    (void)buttonMask; (void)stickX; (void)stickY;
}
