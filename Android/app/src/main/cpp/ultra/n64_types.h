#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. Essential Macros for N64 SDK Headers
#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif

#ifndef _FINALROM
#define _FINALROM
#endif

// 2. Standard library includes
#include <stdint.h>
#include <stddef.h>

// 3. N64 Type Definitions
// These provide the fundamental types (u32, s16, etc.) used by the SDK
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

// 4. SDK Includes
// We include the core ultra64 header which now knows it's in a 'C' environment
#include <ultra64.h> 

// 5. Explicitly include Interface headers if they aren't handled by ultra64.h
// These define 'Gfx', 'Mtx', and 'Acmd'
#include <PR/gbi.h>
#include <PR/abi.h>

// 6. Additional N64 specific headers
#include <PR/sched.h>

#endif // N64_TYPES_H
