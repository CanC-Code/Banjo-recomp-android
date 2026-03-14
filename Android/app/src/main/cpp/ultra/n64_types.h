#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>

// 1. PRIMITIVES
typedef int8_t s8;   typedef uint8_t u8;
typedef int16_t s16; typedef uint16_t u16;
typedef int32_t s32; typedef uint32_t u32;
typedef int64_t s64; typedef uint64_t u64;
typedef float f32;   typedef double f64;
typedef uint8_t uchar;
typedef volatile uint32_t vu32;

// 2. SYSTEM INCLUDES (Safe Namespace)
#ifdef __cplusplus
#include <cstring>
#include <cstdlib>
#include <cmath>
extern "C" {
#else
#include <string.h>
#include <stdlib.h>
#include <math.h>
#endif
extern int sched_yield(void);

// 3. CORE N64 TYPES
typedef void* OSTask;
typedef void* ALHeap;
typedef uint64_t Gfx;
typedef struct { float m[4][4]; } MtxF;
typedef union { struct { int32_t m[4][4]; }; long long force_align; } Mtx;
typedef void* OSMesg;
typedef struct { void* mt; void* full; int32_t count; } OSMesgQueue;
typedef int32_t OSPri;
typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    uint8_t context[512];
} OSThread;

// 4. ANDROID SHIMS
#undef bcopy
#define bcopy(src, dst, n) memmove((dst), (src), (n))

#ifdef __cplusplus
}
#endif

#define _ULTRATYPES_H_ // Block legacy headers
#endif
