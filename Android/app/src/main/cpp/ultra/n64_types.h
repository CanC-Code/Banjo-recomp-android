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
 * 2. CORE N64 PRIMITIVES
 * Defined before includes to resolve circular dependencies in model.h/structs.h
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

// Definition for the 'bool' replacement used by the sanitization script
typedef u8 n64_bool;
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

/** * 3. SYSTEM INCLUDES */
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>

#undef _STRING_H_
#undef __STRING_H__
#undef _SCHED_H_
#undef __SCHED_H__

#include <string.h>
#include <math.h>
#include <sched.h> 

#define _STRING_H_
#define __STRING_H__
#define _SCHED_H_
#define __SCHED_H__

// Fix for NULL issues in legacy C files
#undef NULL
#define NULL 0

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

  #undef bcopy
  #define bcopy(src, dst, n) n64_memmove((dst), (src), (n))
#endif

#endif // N64_TYPES_H
