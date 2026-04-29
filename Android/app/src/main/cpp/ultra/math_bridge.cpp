#include <cmath>
#include <cstring>

extern "C" {

/* =========================
   Basic Vec3f Operations
========================= */

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
    v[0] = v[1] = v[2] = 0.0f;
}

void ml_vec3f_add(float* out, const float* a, const float* b) {
    out[0] = a[0] + b[0];
    out[1] = a[1] + b[1];
    out[2] = a[2] + b[2];
}

void ml_vec3f_sub(float* out, const float* a, const float* b) {
    out[0] = a[0] - b[0];
    out[1] = a[1] - b[1];
    out[2] = a[2] - b[2];
}

void ml_vec3f_scale(float* v, float s) {
    v[0] *= s;
    v[1] *= s;
    v[2] *= s;
}

float ml_vec3f_length(const float* v) {
    return sqrtf(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
}

void ml_vec3f_normalize(float* v) {
    float len = ml_vec3f_length(v);
    if (len > 0.0f) {
        v[0] /= len;
        v[1] /= len;
        v[2] /= len;
    }
}

void ml_vec3f_set_length(float* v, float len) {
    ml_vec3f_normalize(v);
    ml_vec3f_scale(v, len);
}

int ml_isNonzero_vec3f(const float* v) {
    return (v[0] != 0.0f || v[1] != 0.0f || v[2] != 0.0f);
}

/* =========================
   Rotation / Angles
========================= */

void ml_vec3f_yaw_rotate_copy(float* dst, const float* src, float yaw) {
    float c = cosf(yaw);
    float s = sinf(yaw);

    dst[0] = src[0] * c - src[2] * s;
    dst[1] = src[1];
    dst[2] = src[0] * s + src[2] * c;
}

/* =========================
   Matrix
========================= */

void mlMtxIdent(float mtx[4][4]) {
    memset(mtx, 0, sizeof(float) * 16);
    mtx[0][0] = 1.0f;
    mtx[1][1] = 1.0f;
    mtx[2][2] = 1.0f;
    mtx[3][3] = 1.0f;
}

/* =========================
   Math Helpers
========================= */

float gu_sqrtf(float x) {
    return sqrtf(x);
}

}