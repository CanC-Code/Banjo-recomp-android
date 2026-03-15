#ifndef N64_TYPES_H
#define N64_TYPES_H

/**
 * 1. POSIX & NDK CORE HEADERS
 * These must be included FIRST before the blockade to ensure 
 * we use the system's definition of timespec, time_t, etc.
 */
#include <sys/types.h>
#include <sys/stat.h>
#include <time.h>
#include <stddef.h>
#include <stdint.h>

/**
 * 2. THE NUCLEAR BLOCKADE
 * Prevents legacy N64 header files from re-including standard C 
 * headers that clash with the Android NDK.
 */
#define _ULTRA64_H_
#define __ULTRA64_H__
#define _OS_H_
#define __OS_H__
#define _GBI_H_
#define __GBI_H__
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _TIME_H_      // Blocks legacy time.h
#define _SYS_TIME_H_  // Blocks legacy sys/time.h
#define _STDLIB_H_
#define _STRING_H_
#define _BOOL_H_
#define __BOOL_H__

/**
 * 3. CORE N64 SCALAR TYPES
 */
typedef signed char            s8;
typedef unsigned char          u8;
typedef short                  s16;
typedef unsigned short         u16;
typedef int                    s32;
typedef unsigned int           u32;
typedef long long              s64;
typedef unsigned long long     u64;
typedef float                  f32;
typedef double                 f64;
typedef unsigned char          uchar;
typedef volatile unsigned int  vu32; 

typedef int n64_bool;
#ifndef TRUE
  #define TRUE 1
#endif
#ifndef FALSE
  #define FALSE 0
#endif

/**
 * 4. THE "NULL" FIX (Crucial for vegetables.c)
 * Modern NDK Clang defines NULL as ((void*)0).
 * N64 Decomp projects often assign NULL to float variables.
 * We redefine NULL to 0 so it can act as both a pointer and a float 0.0f.
 */
#undef NULL
#define NULL 0

#ifndef M_PI
  #define M_PI 3.14159265358979323846
#endif

/**
 * 5. N64 ENGINE TYPES & ALIGNMENT
 */
#if defined(__GNUC__) || defined(__clang__)
  #define N64_ALIGN(x) __attribute__((aligned(x)))
#else
  #define N64_ALIGN(x)
#endif

typedef u64 OSTime;
typedef u64 Gfx;
typedef u64 Acmd;
typedef s32 OSPri;
typedef s32 OSEvent;
typedef void* OSMesg;
typedef void* OSTask;
typedef void* ALHeap;

typedef struct { s16 state[16]; } ADPCM_STATE;

typedef union N64_ALIGN(8) { 
    struct { s32 m[4][4]; }; 
    long long force_align; 
} Mtx;

typedef struct {
    short ob[3];         
    unsigned short flag; 
    short tc[2];         
    unsigned char cn[4]; 
} Vtx_t;
typedef union N64_ALIGN(8) { Vtx_t v; long long force_align; } Vtx;

typedef struct { void* mt; void* full; s32 count; } OSMesgQueue;

typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errnum;
} OSContPad;

/**
 * 6. AUDIO & THREADING GLOBALS
 * satisfy NativeBridge and Audio HLE requirements
 */
#ifndef _AL_GLOBALS_DEFINED
#define _AL_GLOBALS_DEFINED
typedef struct {
    u8 padding[0x1000]; 
} ALGlobals;
#endif

typedef struct {
    u64 registers[32];
    u64 lo, hi, pc;
} CPUState;

// Forward declarations for common Actor types to prevent "Unknown type" errors
// before the dynamic corrector can inject local typedefs.
typedef struct Actor Actor;
typedef struct sChVegetable sChVegetable;

/**
 * 7. COMPILER MACRO WRAPPERS
 * Scoped to C only to avoid breaking C++ standard libraries
 */
#ifndef __cplusplus
  #define memcpy  n64_memcpy
  #define malloc  n64_malloc
  #define free    n64_free
  #define printf  n64_printf
  #undef bcopy
  #define bcopy(src, dst, n) memmove((dst), (src), (n))
#endif

#endif // N64_TYPES_H
