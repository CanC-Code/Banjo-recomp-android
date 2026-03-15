#ifndef N64_TYPES_H
#define N64_TYPES_H

/**
 * 1. THE NUCLEAR BLOCKADE
 * We define every possible variation of the include guards for N64 headers
 * to prevent the original, conflicting headers from being processed.
 */
#define _ULTRA64_H_
#define __ULTRA64_H__
#define _OS_H_
#define __OS_H__
#define _GBI_H_
#define __GBI_H__
#define _PR_GBI_H_
#define _GU_H_
#define __GU_H__
#define _PR_GU_H_
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _PR_LIBAUDIO_H_
#define _SCHED_H_
#define __SCHED_H__
#define _REGION_H_
#define __REGION_H__
#define _OS_THREAD_H_
#define _OS_MESSAGE_H_
#define _OS_LIBC_H_
#define _STRING_H_
#define __STRING_H__
#define _BOOL_H_      
#define __BOOL_H__
#define BOOL_H

// Comprehensive blockade for osint.h
#define OSINT_H
#define _OSINT_H
#define __OSINT_H
#define _OSINT_H_
#define __OSINT_H__
#define _OS_OSINT_H_
#define __OS_OSINT_H__
#define _ULTRA64_OSINT_H_
#define OSINT_H_INCLUDED
#define _OSINT_H_INCLUDED
#define __OSINT_H_INCLUDED

/** * 2. CORE N64 TYPES 
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

typedef u64 OSTime;
typedef u64 Gfx;
typedef u64 Acmd;
typedef struct { s16 state[16]; } ADPCM_STATE;
typedef union { struct { s32 m[4][4]; }; long long force_align; } Mtx;

// --- Graphics & Lighting ---
typedef struct { u8 col[3]; s8 dir[3]; } Light_t;
typedef union { Light_t l; long long force_align; } Light;
typedef struct { s16 x, y, z; } LookAt_t;
typedef union { LookAt_t l; long long force_align; } LookAt;
typedef struct { s16 x, y, z; } Hilite_t;
typedef union { Hilite_t h; long long force_align; } Hilite;
typedef struct { s32 vp[4]; } Vp_t;
typedef union { Vp_t v; long long force_align; } Vp;

typedef struct {
    short ob[3];         
    unsigned short flag; 
    short tc[2];         
    unsigned char cn[4]; 
} Vtx_t;
typedef union { Vtx_t v; long long force_align; } Vtx;

// --- Controller Data ---
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

// --- OS & Threading ---
typedef void* OSMesg;
typedef struct { void* mt; void* full; s32 count; } OSMesgQueue;
typedef s32 OSPri;
typedef s32 OSEvent;

typedef struct OSTimer_s {
    struct OSTimer_s *next;
    struct OSTimer_s *prev;
    OSTime interval;
    OSTime value;
    OSMesgQueue *mq;
    OSMesg msg;
} OSTimer;

// Fixed: Removed the internal struct tag to avoid "Redefinition of __OSEventState"
typedef struct {
    OSMesgQueue *messageQueue;
    OSMesg message;
} __OSEventState;

#define OS_NUM_EVENTS 15

extern OSTime __osInsertTimer(OSTimer *);
extern OSTimer *__osTimerList;
extern OSTimer __osBaseTimer;
extern __OSEventState __osEventStateTab[OS_NUM_EVENTS];

typedef struct {
    u32 status;
    u32 pc;
    u32 cause;
    u32 badvaddr;
    u64 sp;
    u8 padding[512 - 24]; 
} __OSThreadContext;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    __OSThreadContext context;
} OSThread;

typedef void* OSTask;
typedef void* ALHeap;
typedef struct { u8 d[1024]; } ALGlobals;

typedef struct {
    u64 registers[32];
} CPUState;

/**
 * 3. SYSTEM INCLUDES
 */
#undef _STRING_H_
#undef __STRING_H__
#undef _SCHED_H_
#undef __SCHED_H__

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sched.h> 

#define _STRING_H_
#define __STRING_H__
#define _SCHED_H_
#define __SCHED_H__

// Fix for vegetables.c NULL issue
#undef NULL
#define NULL 0

#ifdef __cplusplus
extern "C" {
#endif

#undef bcopy
#define bcopy(src, dst, n) memmove((dst), (src), (n))

#ifdef __cplusplus
}
#endif

/**
 * 4. COMPILER MACRO WRAPPERS
 */
#ifndef __cplusplus
#define memcpy  n64_memcpy
#define memmove n64_memmove
#define malloc  n64_malloc
#define free    n64_free
#define realloc n64_realloc 
#define calloc  n64_calloc  
#define strcat  n64_strcat
#define strcpy  n64_strcpy
#define strlen  n64_strlen
#define sprintf n64_sprintf
#define printf  n64_printf
#endif

#endif // N64_TYPES_H