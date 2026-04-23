#ifndef N64_TYPES_H
#define N64_TYPES_H

#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif

// Prevent N64 SDK from defining its own conflicting types
#define _ULTRATYPES_H_

#include <stdint.h>
#include <stddef.h>
#include <math.h> // Include system math first

// Correctly sized types for ARM64 Android
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

// Wrap SDK in extern "C" for C++ compatibility
#ifdef __cplusplus
extern "C" {
#endif

#include <ultra64.h> 
#include <PR/sched.h>

#ifdef __cplusplus
}
#endif

#endif // N64_TYPES_H
