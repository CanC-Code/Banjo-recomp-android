#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. System Headers
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
#include <sched.h> 

// 2. N64 Basic Types (MUST BE DEFINED BEFORE ANY SDK INCLUDES)
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

// 3. N64 Kernel/OS Types
typedef s32       OSPri;
typedef u64       OSTime;
typedef u32       OSMesg;

// 4. Collision Fix for 'Image'
#define Image N64Image
typedef struct { u8 dummy; } N64Image;

// 5. Opaque/Stubbed Structs for the SDK
// These prevent the SDK headers from crashing if they can't find definitions
typedef struct { uint8_t dummy[1024]; } ALGlobals;
typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
} OSThread;

typedef uint32_t  u32_ptr;

#endif // N64_TYPES_H
