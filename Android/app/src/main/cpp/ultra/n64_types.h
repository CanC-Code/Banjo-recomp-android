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

// Math constants fallback
#ifndef M_PI
  #define M_PI 3.14159265358979323846
#endif

typedef struct {
    u64 registers[32];
    u64 lo, hi;
    u64 pc;
} CPUState;

#ifdef __cplusplus
extern "C" {
#endif
extern CPUState __osThreadSave;
#ifdef __cplusplus
}
#endif

/**
 * 3. POSIX COMPATIBILITY LAYER
 * Explicitly define timespec and sched_yield for the NDK C++ STL
 */
#include <sys/types.h>

#ifndef _TIMESPEC_DEFINED
#define _TIMESPEC_DEFINED
struct timespec {
    time_t tv_sec;
    long   tv_nsec;
};
#endif

#ifdef __cplusplus
extern "C" {
  int sched_yield(void);
}
#endif

/**
 * 4. C++ HYGIENE & MACRO PROTECTION
 * Prevents project-level macros from breaking the C++ Standard Library.
 */
#ifdef __cplusplus
  #undef vector 
  #undef string
  #undef list
#endif

/**
 * 5. GLOBAL NAMESPACE INJECTION (For C++ Stability)
 */
#ifdef __cplusplus
#include <stddef.h>
extern "C" {
void* memcpy(void* dest, const void* src, size_t n);
void* memmove(void* dest, const void* src, size_t n);
char* strcpy(char* dest, const char* src);
char* strncpy(char* dest, const char* src, size_t n);
char* strcat(char* dest, const char* src);
char* strncat(char* dest, const char* src, size_t n);
size_t strlen(const char* s);
int    strcmp(const char* s1, const char* s2);
int    strncmp(const char* s1, const char* s2, size_t n);
int    memcmp(const void* s1, const void* s2, size_t n);
void* memset(void* s, int c, size_t n);
char* strstr(const char* haystack, const char* needle);
char* strerror(int errnum);

struct tm; 
clock_t clock(void);
double difftime(time_t time1, time_t time0);
time_t mktime(struct tm *timeptr);
time_t time(time_t *timer);
}
#endif

/**
 * 6. SYSTEM INCLUDES
 */
#include <stdint.h>
#include <stdlib.h>

#ifdef __clang__
  #include_next <string.h>
  #include_next <math.h>
#else
  #include <string.h>
  #include <math.h>
#endif

#ifndef NULL
  #define NULL 0
#endif

/**
 * 7. COMPILER MACRO WRAPPERS
 */
#ifndef __cplusplus
  #define memcpy  n64_memcpy
  #define memmove n64_memmove
  #define malloc  n64_malloc
  #define free    n64_free
  #define strcpy  n64_strcpy
  #define strlen  n64_strlen
#endif

#endif // N64_TYPES_H
