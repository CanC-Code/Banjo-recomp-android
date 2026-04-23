#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. Standard library includes
#include <stdint.h>
#include <stddef.h>

// 2. Basic N64 Integer Types
// These are required by almost every other header.
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

// 3. Core N64 Interface Headers
// We include these explicitly to define Gfx, Mtx, Acmd, etc.
// to prevent "unknown type" errors in libaudio.h and gu.h.
#include <PR/gbi.h>
#include <PR/abi.h>

// 4. Master SDK Header
// Now that Gfx/Acmd are defined, this will load correctly.
#include <ultra64.h> 

#endif // N64_TYPES_H
