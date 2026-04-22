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
// These allow the bridge to compile without the full N64 SDK
typedef struct { u32 data[64]; } OSThread;
typedef struct { u32 data[64]; } CPUState;
typedef struct { u64 data; }      Acmd;
typedef struct { u64 data; }      Gfx;
typedef struct { float m[4][4]; } Mtx;
typedef struct { u32 data[32]; } ADPCM_STATE;
typedef struct { u32 data[16]; } LookAt;
typedef struct { u8 dummy; }     Image;

// Recomp-specific pointer type
typedef uint32_t  u32_ptr;

#endif // N64_TYPES_H
