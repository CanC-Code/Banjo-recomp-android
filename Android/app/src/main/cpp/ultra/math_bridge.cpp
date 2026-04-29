#include <math.h>
#include <string.h>
#include <android/log.h>

#define LOG_TAG "BKA_MATH"
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, LOG_TAG, __VA_ARGS__)

extern "C" {

/**
 * ============================
 * Vector (vec3f) Functions
 * ============================
 */

void ml_vec3f_copy(float* dst, const float* src) {
    dst[0] = src[0];
    dst[1] = src[1];
    dst[2] = src[2];
}

void ml_vec3f_set(float* v, float x, float y, float z) {
    v[0] = x;
    v[1] = y;
    v[2] = z;
}

void ml_vec3f_clear(float* v) {
    v[0] = 0.0f;
    v[1] = 0.0f;
    v[2] = 0.0f;
}

void ml_vec3f_add(float* dst, const float* a, const float* b) {
    dst[0] = a[0] + b[0];
    dst[1] = a[1] + b[1];
    dst[2] = a[2] + b[2];
}

void ml_vec3f_sub(float* dst, const float* a, const float* b) {
    dst[0] = a[0] - b[0];
    dst[1] = a[1] - b[1];
    dst[2] = a[2] - b[2];
}

void ml_vec3f_scale(float* v, float s) {
    v[0] *= s;
    v[1] *= s;
    v[2] *= s;
}

float ml_vec3f_dot(const float* a, const float* b) {
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
}

void ml_vec3f_cross(float* dst, const float* a, const float* b) {
    dst[0] = a[1]*b[2] - a[2]*b[1];
    dst[1] = a[2]*b[0] - a[0]*b[2];
    dst[2] = a[0]*b[1] - a[1]*b[0];
}

float ml_vec3f_length(const float* v) {
    return sqrtf(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
}

float ml_vec3f_distance(const float* a, const float* b) {
    float dx = a[0] - b[0];
    float dy = a[1] - b[1];
    float dz = a[2] - b[2];
    return sqrtf(dx*dx + dy*dy + dz*dz);
}

void ml_vec3f_normalize(float* v) {
    float len = ml_vec3f_length(v);
    if (len > 0.0f) {
        float inv = 1.0f / len;
        v[0] *= inv;
        v[1] *= inv;
        v[2] *= inv;
    }
}

void ml_vec3f_set_length(float* v, float len) {
    float current = ml_vec3f_length(v);
    if (current > 0.0f) {
        float scale = len / current;
        ml_vec3f_scale(v, scale);
    }
}

int ml_isNonzero_vec3f(const float* v) {
    return (v[0] != 0.0f || v[1] != 0.0f || v[2] != 0.0f);
}

/**
 * Rotate vector around Y axis (yaw)
 */
void ml_vec3f_yaw_rotate_copy(float* dst, const float* src, float yaw) {
    float s = sinf(yaw);
    float c = cosf(yaw);

    dst[0] = src[0] * c - src[2] * s;
    dst[1] = src[1];
    dst[2] = src[0] * s + src[2] * c;
}


/**
 * ============================
 * Matrix Functions (4x4 float)
 * ============================
 */

void mlMtxIdent(float m[4][4]) {
    memset(m, 0, sizeof(float) * 16);
    m[0][0] = 1.0f;
    m[1][1] = 1.0f;
    m[2][2] = 1.0f;
    m[3][3] = 1.0f;
}

void mlMtxCopy(float dst[4][4], const float src[4][4]) {
    memcpy(dst, src, sizeof(float) * 16);
}

void mlMtxTranslate(float m[4][4], float x, float y, float z) {
    mlMtxIdent(m);
    m[3][0] = x;
    m[3][1] = y;
    m[3][2] = z;
}

void mlMtxScale(float m[4][4], float x, float y, float z) {
    mlMtxIdent(m);
    m[0][0] = x;
    m[1][1] = y;
    m[2][2] = z;
}

void mlMtxMul(float out[4][4], float a[4][4], float b[4][4]) {
    float result[4][4];

    for (int i = 0; i < 4; i++) {
        for (int j = 0; j < 4; j++) {
            result[i][j] =
                a[i][0]*b[0][j] +
                a[i][1]*b[1][j] +
                a[i][2]*b[2][j] +
                a[i][3]*b[3][j];
        }
    }

    memcpy(out, result, sizeof(result));
}


/**
 * ============================
 * Math Wrappers (libultra-like)
 * ============================
 */

float gu_sqrtf(float x) {
    return sqrtf(x);
}

float ml_sin(float x) {
    return sinf(x);
}

float ml_cos(float x) {
    return cosf(x);
}

float ml_atan2f(float y, float x) {
    return atan2f(y, x);
}


/**
 * ============================
 * Safety / Debug Hooks
 * ============================
 */

void ml_math_debug_unimplemented(const char* name) {
    LOGW("Unimplemented math func: %s", name);
}

} // extern "C"