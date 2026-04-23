#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. Standard library includes
#include <stdint.h>
#include <stddef.h>

// 2. N64 Type Definitions (Must be above the SDK includes)
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

// 3. SDK Includes adjusted for your project structure
// 'ultra64.h' is in the '2.0L' folder directly
#include <ultra64.h> 

// 'sched.h' is inside the 'PR' subfolder of '2.0L'
#include <PR/sched.h>

#endif // N64_TYPES_H
