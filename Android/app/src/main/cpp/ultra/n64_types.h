#ifndef N64_TYPES_H
#define N64_TYPES_H

/**
 * 1. THE NUCLEAR BLOCKADE
 * Removed _TIME_H_ and _SYS_TIME_H_ to allow the Android NDK 
 * standard C library to load correctly for C++ wrappers.
 */
#define _ULTRA64_H_
#define _OS_H_
#define _GBI_H_
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _PR_LIBAUDIO_H_

/**
 * 2. CORE N64 SCALARS
 */
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

/**
 * 3. NDK DEFINITIONS
 * Now safe to include without breaking the C++ <ctime> wrappers.
 */
#include <sys/types.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h> 

/**
 * 4. ENGINE STRUCTURES
 */
// Controller Hardware (Fix for 'unknown type name OSContPad')
typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errnum;
} OSContPad;

typedef struct {
    u16 type;
    u8  status;
    u8  errnum;
} OSContStatus;

// Graphics & Audio
typedef u64 Gfx;
typedef u64 Acmd;
typedef void* ALHeap;

typedef struct { s16 state[16]; } ADPCM_STATE;

typedef struct {
    short ob[3];
    unsigned short flag;
    short tc[2];
    unsigned char cn[4];
} Vtx_t;

typedef union { 
    Vtx_t v; 
    long long force_align; 
} Vtx;

typedef union { 
    struct { s32 m[4][4]; }; 
    long long force_align; 
} Mtx;

// Threading & OS
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

// Forward Declarations
typedef struct actor_s Actor; 
typedef struct sChVegetable sChVegetable;

#endif
