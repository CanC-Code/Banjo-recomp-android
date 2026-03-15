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
#define _BOOL_H_      
#define __BOOL_H__
#define BOOL_H
#define OSINT_H
#define _OSINT_H_INCLUDED

/**
 * 2. CORE N64 TYPES
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

typedef int n64_bool;
#ifndef TRUE
  #define TRUE 1
#endif
#ifndef FALSE
  #define FALSE 0
#endif

#ifndef M_PI
  #define M_PI 3.14159265358979323846
#endif

#if defined(__GNUC__) || defined(__clang__)
  #define N64_ALIGN(x) __attribute__((aligned(x)))
#else
  #define N64_ALIGN(x)
#endif

typedef u64 OSTime;
typedef u64 Gfx;
typedef u64 Acmd;
typedef s32 OSPri;
typedef s32 OSEvent;
typedef void* OSMesg;
typedef void* OSTask;
typedef void* ALHeap;

typedef struct { s16 state[16]; } ADPCM_STATE;

typedef union N64_ALIGN(8) { 
    struct { s32 m[4][4]; }; 
    long long force_align; 
} Mtx;

typedef struct {
    short ob[3];         
    unsigned short flag; 
    short tc[2];         
    unsigned char cn[4]; 
} Vtx_t;
typedef union N64_ALIGN(8) { Vtx_t v; long long force_align; } Vtx;

typedef struct { void* mt; void* full; s32 count; } OSMesgQueue;

typedef struct {
    OSMesgQueue *messageQueue;
    OSMesg message;
} __OSEventState;

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
    u64 registers[32];
    u64 lo, hi;
    u64 pc;
} CPUState;

// Provide an opaque ALGlobals definition to satisfy NativeBridge allocation
#ifndef _AL_GLOBALS_DEFINED
#define _AL_GLOBALS_DEFINED
typedef struct {
    u8 padding[0x1000]; // 4KB is safely over-allocated for N64 audio state
} ALGlobals;
#endif

#ifdef __cplusplus
extern "C" {
#endif
extern CPUState __osThreadSave;
#ifdef __cplusplus
}
#endif

/**
 * 3. POSIX COMPATIBILITY LAYER
 */
#include <sys/types.h>
#include <time.h> // Includes native NDK struct timespec, avoiding redefinitions

#ifdef __cplusplus
extern "C" {
  int sched_yield(void);
}
#endif

/**
 * 4. C++ HYGIENE & MACRO PROTECTION
 */
#ifdef __cplusplus
  #undef vector 
  #undef string
  #undef list
#endif

/**
 * 5. COMPILER MACRO WRAPPERS
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

  #undef bcopy
  #define bcopy(src, dst, n) n64_memmove((dst), (src), (n))
#endif

#endif // N64_TYPES_H
