#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. Include standard integer types first
#include <stdint.h>
#include <stddef.h>

// 2. Define the N64-style types before including other headers
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

// 3. Now include the headers that depend on the types above
// This seems to be where line 8 was causing issues
#include <PR/ultra64.h> 
#include <PR/sched.h>

#endif // N64_TYPES_H
