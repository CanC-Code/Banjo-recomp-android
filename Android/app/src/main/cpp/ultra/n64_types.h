#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. Force load system headers first to prevent collisions with N64 headers
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
#include <sched.h> // Essential for sched_yield()

// 2. Standard N64 Fixed-Width Types
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

// 3. Missing Kernel Types
typedef s32       OSPri;
typedef u64       OSTime;
typedef u32       OSMesg;

// 4. Verification Stubs
typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    u32 context; 
} OSThread;

// Define a placeholder for ALGlobals if not included yet
typedef struct { uint8_t dummy[1024]; } ALGlobals;

typedef struct { u32 data[64]; } CPUState;
typedef struct { u64 data; }      Acmd;
typedef struct { u64 data; }      Gfx;
typedef struct { float m[4][4]; } Mtx;
typedef struct { u32 data[16]; } LookAt;
typedef struct { u32 data[16]; } Hilite;
typedef struct { u32 data[16]; } Light;
typedef struct { u32 data[16]; } OSTask;
typedef struct { u32 data[16]; } OSMesgQueue;
typedef struct { u32 data[16]; } uSprite;

// 5. Collision Fix for 'Image'
// This renames 'Image' to 'N64Image' globally to avoid the clash with system types
#define Image N64Image
typedef struct { u8 dummy; } N64Image;

typedef uint32_t  u32_ptr;

#endif // N64_TYPES_H
