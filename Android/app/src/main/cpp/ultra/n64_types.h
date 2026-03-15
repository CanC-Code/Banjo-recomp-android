#ifndef N64_TYPES_H
#define N64_TYPES_H

/**
 * 1. THE NUCLEAR BLOCKADE
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
#define OSINT_H
#define _OSINT_H_INCLUDED

/**
 * 2. CORE N64 PRIMITIVES & ALIGNMENT
 * These MUST be defined before any #include to prevent circular dependency errors 
 * in headers like model.h or structs.h.
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

#if defined(__GNUC__) || defined(__clang__)
#define N64_ALIGN(x) __attribute__((aligned(x)))
#else
#define N64_ALIGN(x)
#endif

typedef u64 OSTime;
typedef u64 Gfx;
typedef u64 Acmd;

typedef struct { s16 state[16]; } ADPCM_STATE;

typedef union N64_ALIGN(8) { 
    struct { s32 m[4][4]; }; 
    long long force_align; 
} Mtx;

typedef struct { u8 col[3]; s8 dir[3]; } Light_t;
typedef union N64_ALIGN(8) { Light_t l; long long force_align; } Light;
typedef struct { s16 x, y, z; } LookAt_t;
typedef union N64_ALIGN(8) { LookAt_t l; long long force_align; } LookAt;
typedef struct { s16 x, y, z; } Hilite_t;
typedef union N64_ALIGN(8) { Hilite_t h; long long force_align; } Hilite;
typedef struct { s32 vp[4]; } Vp_t;
typedef union N64_ALIGN(8) { Vp_t v; long long force_align; } Vp;

typedef struct {
    short ob[3];         
    unsigned short flag; 
    short tc[2];         
    unsigned char cn[4]; 
} Vtx_t;
typedef union N64_ALIGN(8) { Vtx_t v; long long force_align; } Vtx;

/** * 3. SYSTEM INCLUDES
 * Now that primitives are defined, it is safe to load system headers.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>

/* Temporarily lift blockade to allow the real string/math/sched headers to load */
#undef _STRING_H_
#undef __STRING_H__
#undef _SCHED_H_
#undef __SCHED_H__

#include <string.h>
#include <math.h>
#include <sched.h> 

/* Re-establish blockade */
#define _STRING_H_
#define __STRING_H__
#define _SCHED_H_
#define __SCHED_H__

/**
 * 4. OS & THREADING STRUCTURES
 */
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

typedef struct {
    OSMesgQueue *messageQueue;
    OSMesg message;
} __OSEventState;

#define OS_NUM_EVENTS 15
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

typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errnum;
} OSContPad;

/**
 * 5. COMPILER MACRO WRAPPERS
 */
#ifndef __cplusplus
#undef NULL
#define NULL 0

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

#undef bcopy
#define bcopy(src, dst, n) n64_memmove((dst), (src), (n))
#endif

#endif // N64_TYPES_H
