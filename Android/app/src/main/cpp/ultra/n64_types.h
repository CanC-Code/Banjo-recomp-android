#ifndef N64_TYPES_H
#define N64_TYPES_H

/** * 1. ATOMIC PRIMITIVES 
 * These must be defined first. If a legacy header hijacks the include 
 * chain later, these types will already be locked into the compiler.
 */
typedef signed char            s8;
typedef unsigned char          u8;
typedef short                  s16;
typedef unsigned short         u16;
typedef int                    s32;
typedef unsigned int           u32;
typedef long long              s64;
typedef unsigned long long     u64;
typedef float                  f32;
typedef double                 f64;
typedef unsigned char          uchar;
typedef volatile uint32_t      vu32;

/**
 * 2. THE ABSOLUTE BLOCKADE
 * We define these guards immediately. This ensures that if any file 
 * tries to #include <PR/os.h> or similar, the compiler sees the guard
 * is already set and skips the file entirely.
 */
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
#define _REGION_H_
#define __REGION_H__
#define _OS_THREAD_H_
#define _OS_MESSAGE_H_
#define _OS_LIBC_H_
#define _STRING_H_
#define __STRING_H__

// 3. SAFE SYSTEM INCLUDES
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

// 4. N64 CORE STRUCTURES
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

// Android memmove shim
#undef bcopy
#define bcopy(src, dst, n) memmove((dst), (src), (n))

#ifdef __cplusplus
}
#endif

#endif // N64_TYPES_H
