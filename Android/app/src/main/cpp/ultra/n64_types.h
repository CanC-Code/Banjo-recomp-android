#ifndef N64_TYPES_H
#define N64_TYPES_H

#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif

#define _ULTRATYPES_H_

#include <stdint.h>
#include <stddef.h>
#include <math.h> 

// Android's strings.h defines these as macros which break N64's os_libc.h
// We must undefine them before including N64 headers.
#ifdef bcopy
#undef bcopy
#endif
#ifdef bzero
#undef bzero
#endif
#ifdef bcmp
#undef bcmp
#endif

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

#ifdef __cplusplus
extern "C" {
#endif

// We must include the base OS types before ultra64.h to satisfy OSPiHandle
#include <PR/os_pi.h>
#include <ultra64.h> 
#include <PR/sched.h>

// Renamed from ALGlobals to avoid collision with libaudio.h
typedef struct {
    uint32_t* screenBuffer; 
    uint32_t frameCount;
} AndroidBridgeGlobals;

#ifdef __cplusplus
}
#endif

#undef NULL
#define NULL 0

#endif // N64_TYPES_H
