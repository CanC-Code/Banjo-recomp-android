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
#define _GBI_H_
#define _LIBAUDIO_H_

// 2. CORE N64 SCALARS
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

// 3. CORE STRUCT DEFINITIONS
typedef struct {
    u64 registers[32];
    u64 lo, hi, pc;
    u32 status; // <--- ADDED: Required by exceptasm.cpp
    u32 cause;
    u32 badvaddr;
} CPUState;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    CPUState context;
    u8 padding[512];
} OSThread;

// 4. MESSAGE & TASK TYPES (Required for sched.h)
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
