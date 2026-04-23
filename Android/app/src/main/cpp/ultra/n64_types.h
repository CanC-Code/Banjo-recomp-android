#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>

// Standard N64 Fixed-Width Types
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

// --- Verification Stubs ---
typedef struct OSThread_s {
    struct OSThread_s *next;
    s32 priority;
    u32 context; // Simplified for stub
} OSThread;

typedef struct { u32 data[64]; } CPUState;
typedef struct { u64 data; }      Acmd;
typedef struct { u64 data; }      Gfx;
typedef struct { float m[4][4]; } Mtx;
typedef struct { u32 data[32]; } ADPCM_STATE;
typedef struct { u32 data[16]; } LookAt;
typedef struct { u32 data[16]; } Hilite;
typedef struct { u32 data[16]; } Light;
typedef struct { u32 data[16]; } OSTask;
typedef struct { u32 data[16]; } OSMesgQueue;
typedef u32 OSMesg;
typedef u64 OSTime;
typedef struct { u32 data[16]; } uSprite;

// Prevent redefinition of Image if gu.h is included
#define _IMAGE_H_
typedef struct { u8 dummy; } Image;

// Recomp-specific pointer type
typedef uint32_t  u32_ptr;

#endif // N64_TYPES_H
