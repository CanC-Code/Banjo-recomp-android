#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. Essential Macros for N64 SDK Headers
#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif

#ifndef _FINALROM
#define _FINALROM
#endif

// Tell the N64 SDK NOT to define its own types, as they conflict 
// with modern 64-bit architectures (Android arm64).
#define _ULTRATYPES_H_

// 2. Standard library includes
#include <stdint.h>
#include <stddef.h>
#include <math.h> // Include standard math before SDK to prevent cosf/sinf clashes

// 3. N64 Type Definitions mapped to strict sizes
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

// Add volatile types just in case the SDK needs them
typedef volatile uint8_t   vu8;
typedef volatile uint16_t  vu16;
typedef volatile uint32_t  vu32;
typedef volatile uint64_t  vu64;

typedef volatile int8_t    vs8;
typedef volatile int16_t   vs16;
typedef volatile int32_t   vs32;
typedef volatile int64_t   vs64;

// 4. SDK Includes inside extern "C" to tell the C++ compiler these are C headers
#ifdef __cplusplus
extern "C" {
#endif

#include <ultra64.h> 
#include <PR/gbi.h>
#include <PR/abi.h>
#include <PR/sched.h>

#ifdef __cplusplus
}
#endif

#endif // N64_TYPES_H
