#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. POSIX FIRST: Get the system's timespec before any N64 headers clash
#include <sys/types.h>
#include <time.h>
#include <stddef.h>
#include <stdint.h>

// 2. THE NUCLEAR BLOCKADE
#define _TIME_H_
#define _SYS_TIME_H_
#define _ULTRA64_H_
#define _OS_H_
#define _GBI_H_
#define _LIBAUDIO_H_

// 3. SCALARS & NULL FIX
typedef signed char s8;
typedef unsigned char u8;
typedef short s16;
typedef unsigned short u16;
typedef int s32;
typedef unsigned int u32;
typedef long long s64;
typedef unsigned long long u64;
typedef float f32;
typedef double f64;
typedef int n64_bool;

#undef NULL
#define NULL 0 // Allows NULL to act as both 0 (pointer) and 0.0f (float)

// 4. ENGINE STUBS
typedef u64 OSTime;
typedef void* OSMesg;
#ifndef _AL_GLOBALS_DEFINED
  #define _AL_GLOBALS_DEFINED
  typedef struct { u8 padding[0x1000]; } ALGlobals;
#endif

typedef struct Actor Actor;
typedef struct sChVegetable sChVegetable;

#endif
