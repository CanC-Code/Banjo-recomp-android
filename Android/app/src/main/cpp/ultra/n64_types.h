#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>

// Standard N64 Type Definitions for modern systems
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

// Recomp-specific pointer types (adjust if your project uses different mapping)
typedef uint32_t  u32_ptr;

#endif // N64_TYPES_H
