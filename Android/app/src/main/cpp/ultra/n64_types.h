#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>

// 1. Primitive Type Definitions (The core requirement for the recompilation)
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
typedef s32       n64_bool;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

// 2. Forward Declarations
// This tells the compiler these types exist elsewhere without needing to include
// the heavy SDK headers here, which prevents the circular include loop.
struct OSPiHandle_s;
typedef struct OSPiHandle_s OSPiHandle;
struct OSIoMesg_s;
typedef struct OSIoMesg_s OSIoMesg;

// 3. Bridge Structure (Renamed to avoid conflict with N64 Audio Library)
#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t* screenBuffer; // Pointer to the 320x240 RGBA pixels
    uint32_t frameCount;
} AndroidBridgeGlobals;

#ifdef __cplusplus
}
#endif

#undef NULL
#define NULL 0

#endif // N64_TYPES_H
