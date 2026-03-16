#ifndef N64_TYPES_H
#define N64_TYPES_H

// 1. THE NUCLEAR BLOCKADE (MOVED TO ABSOLUTE TOP)
// We must block the legacy N64 headers *before* including any system headers.
// This prevents hijacked headers from successfully chaining into libaudio.h
#define _ULTRA64_H_
#define _OS_H_
#define _GBI_H_
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _PR_LIBAUDIO_H_

// 2. SYSTEM INCLUDES
// Now safe to include. If local time.h hijacks, it hits the blockade above and stops safely.
#include <sys/types.h>
#include <time.h>
#include <stddef.h>
#include <stdint.h>

// Lock out time headers to prevent further legacy clashes down the line
#define _TIME_H_
#define _SYS_TIME_H_

// 3. COMPLETE TYPE DEFINITIONS
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

#endif
