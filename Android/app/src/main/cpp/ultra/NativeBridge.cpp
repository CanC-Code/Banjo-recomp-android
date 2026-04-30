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
#include <stdatomic.h>

// Include the register definitions from File 1
#include "n64_registers.h" // Replace with the actual header name

#define TAG "BKA-NativeBridge"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  TAG, __VA_ARGS__)

// -----------------------------------------------------------------------
// Module-level state
// -----------------------------------------------------------------------
static jobject   g_service_ref  = nullptr;
static jmethodID g_progress_mid = nullptr;
static GLuint    g_fb_texture   = 0;
static GLuint    g_quad_prog    = 0;

static atomic_bool g_surface_ready  = ATOMIC_VAR_INIT(false);
static atomic_bool g_globals_ready  = ATOMIC_VAR_INIT(false);

// Extern declaration for gBridgeGlobals (defined elsewhere)
extern AndroidBridgeGlobals* gBridgeGlobals;

extern "C" {
    // Exported for LinkerSymbols.cpp
    extern uint32_t* gN64_Reg_Base; // Defined in File 1

    extern void initInterruptTables();
    extern void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize);
    extern void run_native_otr_generation_with_callback(
        JNIEnv* env, jobject callbackObj, jmethodID progressMid,
        int romFd, uint8_t* manifestPtr, uint32_t manifestSize,
        const char* outDirPath);
    extern void mainLoop();
}

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
        gBridgeGlobals->screenBuffer = (uint32_t*)malloc(320u * 240u * sizeof(uint32_t));
        if (!gBridgeGlobals->screenBuffer) {
            LOGE("ensureBridgeGlobals: screenBuffer malloc failed");
            return;
        }
        // Fill with opaque red for initial rendering check
        for (int i = 0; i < 320 * 240; i++) {
            gBridgeGlobals->screenBuffer[i] = 0xFF0000FFu;
        }
    }
    atomic_store(&g_globals_ready, true);
}

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

static GLuint buildQuadProgram() {
    const char* vsrc = "#version 300 es\n"
        "in vec2 aPos; in vec2 aUV; out vec2 vUV;\n"
        "void main() { gl_Position = vec4(aPos, 0.0, 1.0); vUV = aUV; }\n";

    const char* fsrc = "#version 300 es\n"
        "precision mediump float; in vec2 vUV; uniform sampler2D uTex; out vec4 fragColor;\n"
        "void main() { fragColor = texture(uTex, vUV); }\n";

    GLuint vs = compileShader(GL_VERTEX_SHADER,   vsrc);
    GLuint fs = compileShader(GL_FRAGMENT_SHADER, fsrc);
    if (!vs || !fs) return 0;

    GLuint prog = glCreateProgram();
    glAttachShader(prog, vs); glAttachShader(prog, fs);
    glBindAttribLocation(prog, 0, "aPos"); glBindAttribLocation(prog, 1, "aUV");
    glLinkProgram(prog);

    GLint ok = 0;
    glGetProgramiv(prog, GL_LINK_STATUS, &ok);
    if (!ok) { glDeleteProgram(prog); return 0; }
    glDeleteShader(vs); glDeleteShader(fs);
    return prog;
}

extern "C" JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeInit(JNIEnv* env, jclass, jobject serviceObj) {
    // Check if gN64_Reg_Base is initialized
    if (!gN64_Reg_Base) {
        LOGE("gN64_Reg_Base is NULL! Cannot initialize registers.");
        return;
    }
    LOGI("gN64_Reg_Base = %p", gN64_Reg_Base);

    if (g_service_ref != nullptr) {
        env->DeleteGlobalRef(g_service_ref);
    }
    g_service_ref = env->NewGlobalRef(serviceObj);
    jclass cls = env->GetObjectClass(g_service_ref);
    g_progress_mid = env->GetMethodID(cls, "updateOtrProgress", "(ILjava/lang/String;)V");

    ensureBridgeGlobals();
    LOGI("nativeInit: Bridge and Hardware Traps ready");
}

extern "C" JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_runOtrGeneration(JNIEnv* env, jclass, jint romFd, jobject assetManager, jstring outDir) {
    if (!gN64_Reg_Base) {
        LOGE("gN64_Reg_Base is NULL in runOtrGeneration!");
        return;
    }

    const char* nativeOutDir = env->GetStringUTFChars(outDir, nullptr);
    AAssetManager* mgr = AAssetManager_fromJava(env, assetManager);
    AAsset* asset = AAssetManager_open(mgr, "manifest_us.bin", AASSET_MODE_BUFFER);
    if (asset) {
        run_native_otr_generation_with_callback(
            env, g_service_ref, g_progress_mid, (int)romFd,
            (uint8_t*)AAsset_getBuffer(asset), (uint32_t)AAsset_getLength(asset),
            nativeOutDir);
        AAsset_close(asset);
    }
    env->ReleaseStringUTFChars(outDir, nativeOutDir);
}

extern "C" JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass, jstring otrPathJ, jobject assetManager) {
    if (!gN64_Reg_Base) {
        LOGE("gN64_Reg_Base is NULL in nativeGameBoot!");
        return;
    }

    ensureBridgeGlobals();
    initInterruptTables();

    const char* assetDir = env->GetStringUTFChars(otrPathJ, nullptr);
    AAssetManager* mgr = AAssetManager_fromJava(env, assetManager);
    AAsset* manifestAsset = AAssetManager_open(mgr, "manifest_us.bin", AASSET_MODE_BUFFER);
    if (manifestAsset) {
        ResourceMgr_Init(
            assetDir,
            (uint8_t*)AAsset_getBuffer(manifestAsset),
            (uint32_t)AAsset_getLength(manifestAsset));
        AAsset_close(manifestAsset);
    } else {
        ResourceMgr_Init(assetDir, nullptr, 0);
    }
    env->ReleaseStringUTFChars(otrPathJ, assetDir);
    mainLoop();
}

extern "C" JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_surfaceReady(JNIEnv*, jclass, jint width, jint height) {
    if (g_quad_prog == 0) {
        g_quad_prog = buildQuadProgram();
    }
    if (g_fb_texture != 0) {
        glDeleteTextures(1, &g_fb_texture);
    }
    glGenTextures(1, &g_fb_texture);
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, 320, 240, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    atomic_store(&g_surface_ready, true);
}

extern "C" JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_updateTexture(JNIEnv*, jclass, jint) {
    if (!atomic_load(&g_surface_ready) || !atomic_load(&g_globals_ready)) {
        return;
    }
    glBindTexture(GL_TEXTURE_2D, g_fb_texture);
    glTexSubImage2D(
        GL_TEXTURE_2D, 0, 0, 0, 320, 240,
        GL_RGBA, GL_UNSIGNED_BYTE, gBridgeGlobals->screenBuffer);
    glClear(GL_COLOR_BUFFER_BIT);
    glUseProgram(g_quad_prog);
    static const float kVerts[] = {
        -1.f, -1.f, 0.f, 1.f,
         1.f, -1.f, 1.f, 1.f,
        -1.f,  1.f, 0.f, 0.f,
         1.f,  1.f, 1.f, 0.f
    };
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, kVerts);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, kVerts + 2);
    glEnableVertexAttribArray(0);
    glEnableVertexAttribArray(1);
    glDrawArrays(GL_TRIANGLE_STRIP, 0, 4);
}

extern "C" JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeUpdateInput(JNIEnv*, jclass, jint, jfloat, jfloat) {}