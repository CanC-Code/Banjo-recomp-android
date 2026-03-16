#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. COMPLETE TYPE DEFINITIONS
// Moved entirely above system includes so any hijacked headers
// already have the full context they need to compile safely.

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

// Audio & Graphics Types
typedef u64 Gfx;
typedef u64 Acmd;
typedef struct { s16 state[16]; } ADPCM_STATE;

#ifndef _AL_GLOBALS_DEFINED
#define _AL_GLOBALS_DEFINED
typedef struct { u8 padding[0x1000]; } ALGlobals;
#endif

// Threading & OS Types
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

// Forward Declarations
typedef struct Actor Actor;
typedef struct sChVegetable sChVegetable;


// 2. SYSTEM INCLUDES
// Safe to call now; if it hijacks into local files, the types above satisfy them.
#include <sys/types.h>
#include <time.h>
#include <stddef.h>
#include <stdint.h>


// 3. THE NUCLEAR BLOCKADE
// Safely silences legacy N64 includes downstream
#define _TIME_H_
#define _SYS_TIME_H_
#define _ULTRA64_H_
#define _OS_H_
#define _GBI_H_
#define _LIBAUDIO_H_

#endif
