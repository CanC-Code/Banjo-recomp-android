#ifndef N64_TYPES_H
#define N64_TYPES_H

#ifdef __cplusplus
extern "C" {
#endif

#define _ULTRA64_H_
#define _OS_H_
#define _GBI_H_
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _PR_LIBAUDIO_H_

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

typedef u64 OSTime;
typedef void* OSMesg;
typedef void* OSTask;

typedef struct OSMesgQueue_s {
    void* mt;
    void* full;
    s32 count;
} OSMesgQueue;

typedef struct {
    u64 registers[32];
    u64 lo, hi, pc;
    u32 status, cause, badvaddr;
} CPUState;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    CPUState context;
    u8 padding[512];
} OSThread;

typedef struct { u16 button; s8 stick_x, stick_y; u8 errnum; } OSContPad;
typedef struct { u16 type; u8 status, errnum; } OSContStatus;

typedef u64 Gfx;
typedef u64 Acmd;
typedef void* ALHeap;
typedef struct { s16 state[16]; } ADPCM_STATE;

typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef union { Vtx_t v; long long force_align; } Vtx;
typedef union { struct { s32 m[4][4]; }; long long force_align; } Mtx;

#ifndef _AL_GLOBALS_DEFINED
#define _AL_GLOBALS_DEFINED
typedef struct { u8 padding[0x1000]; } ALGlobals;
#endif

typedef struct actor_s Actor; 
typedef struct sChVegetable sChVegetable;

#ifdef __cplusplus
}
#endif

#include <sys/types.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>
#include <sched.h> 
#include <math.h>

#ifndef M_PI
  #define M_PI 3.14159265358979323846
#endif

#endif
