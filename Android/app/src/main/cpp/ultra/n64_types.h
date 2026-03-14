#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. FORCE SYSTEM HEADERS NOW
// We include these before any blockade to ensure Android system functions are defined.
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

// 2. PRIMITIVES
typedef int8_t s8;   typedef uint8_t u8;
typedef int16_t s16; typedef uint16_t u16;
typedef int32_t s32; typedef uint32_t u32;
typedef int64_t s64; typedef uint64_t u64;
typedef float f32;   typedef double f64;
typedef uint8_t uchar;
typedef volatile uint32_t vu32;

#ifdef __cplusplus
extern "C" {
#endif

// 3. INJECT MISSING TYPES (Found in your error log)
typedef uint64_t Gfx;
typedef uint64_t Acmd;
typedef struct { int16_t state[16]; } ADPCM_STATE;
typedef struct { float m[4][4]; } MtxF;
typedef union { struct { int32_t m[4][4]; }; long long force_align; } Mtx;

typedef struct { uint8_t col[3]; int8_t dir[3]; } Light_t;
typedef union { Light_t l; long long force_align; } Light;
typedef struct { int16_t x, y, z; } LookAt_t;
typedef union { LookAt_t l; long long force_align; } LookAt;
typedef struct { int16_t x, y, z; } Hilite_t;
typedef union { Hilite_t h; long long force_align; } Hilite;
typedef struct { int32_t vp[4]; } Vp_t;
typedef union { Vp_t v; long long force_align; } Vp;

// OS & Threading
typedef void* OSMesg;
typedef struct { void* mt; void* full; int32_t count; } OSMesgQueue;
typedef int32_t OSPri;
typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    uint8_t context[512];
} OSThread;

typedef void* OSTask;
typedef void* ALHeap;
typedef struct { uint8_t d[1024]; } ALGlobals;

#ifdef __cplusplus
}
#endif

// 4. THE GREAT WALL (Blockade)
// We use every possible variation of N64 guards to ensure legacy headers are skipped.
#define _ULTRA64_H_
#define __ULTRA64_H__
#define _OS_H_
#define __OS_H__
#define _GBI_H_
#define __GBI_H__
#define _PR_GBI_H_
#define _GU_H_
#define __GU_H__
#define _PR_GU_H_
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _PR_LIBAUDIO_H_
#define _SCHED_H_
#define __SCHED_H__
#define _OS_THREAD_H_
#define _OS_MESSAGE_H_
#define _OS_LIBC_H_
#define _STRING_H_
#define __STRING_H__

// 5. ANDROID SHIMS
#undef bcopy
#define bcopy(src, dst, n) memmove((dst), (src), (n))

#endif // N64_TYPES_H
