#ifndef N64_TYPES_H
#define N64_TYPES_H

/** * 1. TRUE ATOMIC PRIMITIVES & N64 STRUCTURES */
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
 * 2. THE ABSOLUTE BLOCKADE
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

#ifndef TRUE
#define TRUE 1
#endif

#ifndef FALSE
#define FALSE 0
#endif

/**
 * 3. SAFE SYSTEM INCLUDES
 * Placed here so the system <string.h> loads BEFORE we hijack the functions.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * 4. FOOLPROOF COMPILER MACRO HIJACK
 * This forces the compiler to immediately rename the conflicting legacy C 
 * functions in-memory before evaluating the game files. This ensures no conflicts
 * with the system headers without relying on external python scripts.
 */
#define memcpy  n64_memcpy
#define memmove n64_memmove
#define malloc  n64_malloc
#define free    n64_free
#define strcat  n64_strcat
#define strcpy  n64_strcpy
#define strlen  n64_strlen
#define sprintf n64_sprintf
#define printf  n64_printf

#undef bcopy
// We map the old N64 bcopy directly to the n64_memmove we just hijacked
#define bcopy(src, dst, n) n64_memmove((dst), (src), (n))

#ifdef __cplusplus
}
#endif

#endif // N64_TYPES_H
