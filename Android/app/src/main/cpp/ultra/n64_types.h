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
    u32 status;
    u32 PC;
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

/**
 * 3. SYSTEM INCLUDES
 * include_next is critical here. It tells the compiler to skip your local 
 * [span_6](start_span)include directory and find the actual NDK system headers[span_6](end_span).
 */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>

#undef _STRING_H_
#undef __STRING_H__
#undef _SCHED_H_
#undef __SCHED_H__

#ifdef __clang__
  #include_next <string.h>
  #include_next <math.h>
  #include_next <sched.h>
#else
  #include <string.h>
  #include <math.h>
  #include <sched.h>
#endif

#define _STRING_H_
#define __STRING_H__
#define _SCHED_H_
#define __SCHED_H__

#undef NULL
#define NULL 0

/**
 * 4. N64 NAMESPACED SYMBOLS
 * Only define these as macros for C code. Renaming them via macros in C++ 
 * [span_7](start_span)causes the "no member in global namespace" errors in the STL[span_7](end_span).
 */
#ifdef __cplusplus
extern "C" {
#endif

extern void* n64_memcpy(void* dest, const void* src, size_t n);
extern void* n64_memmove(void* dest, const void* src, size_t n);
extern void* n64_malloc(size_t size);
extern void  n64_free(void* ptr);
extern void* n64_realloc(void* ptr, size_t size);
extern void* n64_calloc(size_t nmemb, size_t size);
extern char* n64_strcat(char* dest, const char* src);
extern char* n64_strcpy(char* dest, const char* src);
extern size_t n64_strlen(const char* s);
extern int   n64_sprintf(char* str, const char* format, ...);
extern int   n64_printf(const char* format, ...);

#undef bcopy
#define bcopy(src, dst, n) n64_memmove((dst), (src), (n))

#ifdef __cplusplus
}
#else
  // Only use macro redefinition in pure C files
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
