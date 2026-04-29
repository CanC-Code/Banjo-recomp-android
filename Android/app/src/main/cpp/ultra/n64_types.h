#ifndef N64_TYPES_H
#define N64_TYPES_H

#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif

// Prevent N64 SDK from defining its own basic types (u8, u32, etc)
// which would conflict with our ARM64-safe ones below.
#define _ULTRATYPES_H_

#include <stdint.h>
#include <stddef.h>
#include <math.h>

// --- Basic N64 Types (Mapped for ARM64) ---
typedef uint8_t   u8;
typedef uint16_t  u16;
typedef uint32_t  u32;
typedef uint64_t  u64;
typedef int8_t    s8;
typedef int16_t   s16;
typedef int32_t   s32;
typedef int64_t   s64;
typedef float     f32;
typedef double    f64;
typedef s32       n64_bool;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

// --- Bridge Globals ---
#ifdef __cplusplus
extern "C" {
#endif

// We include the main SDK headers here. 
// They will now provide Gfx, Mtx, Vp, and OS structures without clashing.
#include <ultra64.h>
#include <PR/sched.h>

typedef struct {
    uint32_t* screenBuffer;
    uint32_t frameCount;
} AndroidBridgeGlobals;

#ifdef __cplusplus
}
#endif

// Restore legacy N64 NULL definition for float initializers
#undef NULL
#define NULL 0

#endif // N64_TYPES_H
