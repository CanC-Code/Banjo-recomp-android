#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <sys/types.h>
#include <time.h>
#include <stddef.h>
#include <stdint.h>

// 1. THE NUCLEAR BLOCKADE
#define _TIME_H_
#define _SYS_TIME_H_
#define _ULTRA64_H_
#define _OS_H_

// 2. CORE N64 TYPES
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
#define NULL 0

// 3. FULL STRUCT DEFINITIONS (Required for C++ compilation)
typedef struct {
    u64 registers[32];
    u64 lo, hi, pc;
} CPUState;

typedef struct OSThread_s {
    struct OSThread_s *next;
    s32 priority;
    CPUState context;
    u8 padding[512]; // Opaque padding for OS-specific thread data
} OSThread;

typedef u64 OSTime;
typedef void* OSMesg;

#ifndef _AL_GLOBALS_DEFINED
#define _AL_GLOBALS_DEFINED
typedef struct { u8 padding[0x1000]; } ALGlobals;
#endif

// 4. FORWARD DECLARATIONS
typedef struct Actor Actor;
typedef struct sChVegetable sChVegetable;

#endif
