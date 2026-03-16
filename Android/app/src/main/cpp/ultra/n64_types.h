#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. CORE N64 SCALARS
// These MUST be at the very top so that if local headers (like include/time.h)
// hijack the include paths, they already know what u8 and s32 are.
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
typedef s32 OSPri;

#undef NULL
#define NULL 0

// 2. SYSTEM INCLUDES
#include <sys/types.h>
#include <time.h>
#include <stddef.h>
#include <stdint.h>

// 3. THE NUCLEAR BLOCKADE
#define _TIME_H_
#define _SYS_TIME_H_
#define _ULTRA64_H_
#define _OS_H_
#define _GBI_H_
#define _LIBAUDIO_H_

// 4. CORE STRUCT DEFINITIONS
typedef struct {
    u64 registers[32];
    u64 lo, hi, pc;
    u32 status;
    u32 cause;
    u32 badvaddr;
} CPUState;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    CPUState context;
    u8 padding[512];
} OSThread;

typedef u64 OSTime;
typedef void* OSMesg;
typedef void* OSTask;

typedef struct OSMesgQueue_s {
    void* mt;
    void* full;
    s32 count;
} OSMesgQueue;

#ifndef _AL_GLOBALS_DEFINED
#define _AL_GLOBALS_DEFINED
typedef struct { u8 padding[0x1000]; } ALGlobals;
#endif

// 5. FORWARD DECLARATIONS
typedef struct Actor Actor;
typedef struct sChVegetable sChVegetable;

#endif
