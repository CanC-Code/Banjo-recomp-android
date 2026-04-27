#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H

/* =============================================
   PREPROCESSOR INTERCEPTION
   Force-included via -include before every TU (both C and C++).
   Order matters: all blocking #defines must precede all #includes.
   ============================================= */

/* --- Block ultratypes.h (all known guard variants) --- */
#define _ULTRA64_TYPES_H_  1
#define _ULTRATYPES_H_     1
#define _PR_ULTRATYPES_H_  1
#define ULTRATYPES_H       1

/* --- Block include/structs.h ---
   structs.h chains into ultra64.h and core2/vla.h -> ultratypes.h (missing).
   Must be defined before any include that might reach structs.h. */
#define _STRUCTS_H_        1
#define STRUCTS_H          1
#define _BKA_STRUCTS_H_    1

/* --- Block core2/vla.h (belt and braces) --- */
#define _VLA_H_            1
#define VLA_H              1
#define _CORE2_VLA_H_      1
#define CORE2_VLA_H        1
#define _BKA_VLA_GUARD_    1

/* --- Block os_message.h and os_pi.h ---
   We define these types ourselves below. */
#define _OS_MESSAGE_H_     1
#define _OS_PI_H_          1
#define _PR_OS_MESSAGE_H_  1
#define _PR_OS_PI_H_       1

/* --- Language / GBI flags ---
   _LANGUAGE_C_PLUS_PLUS must only be defined for C++ TUs.
   Plain C files (e.g. bigalligator.c) get extern "C" syntax errors otherwise. */
#define _LANGUAGE_C 1
#ifdef __cplusplus
#define _LANGUAGE_C_PLUS_PLUS 1
#endif
#define F3DEX_GBI_2 1

/* --- Block PR/abi.h's Acmd --- */
#define Acmd BKA_Acmd_Compat

/* --- Intercept conflicting AL types ---
   ALGlobals / ALGlobals_s intentionally NOT touched here.
   - stubs.cpp: uses ALGlobals* (pointer only) — passes fine already.
   - NativeBridge.cpp: uses sizeof(ALGlobals) — needs the full definition
     from libaudio.h. Any forward-decl or typedef we add here conflicts
     with libaudio.h's anonymous-struct typedef and breaks NativeBridge.
     Solution: define nothing for ALGlobals; let libaudio.h own it fully. */
#define ALLink_s             __orig_ALLink_s
#define ALLink               __orig_ALLink
#define ALVoice_s            __orig_ALVoice_s
#define ALVoice              __orig_ALVoice
#define N_ALVoice_s          __orig_N_ALVoice_s
#define N_ALVoice            __orig_N_ALVoice
#define ALSynth              __orig_ALSynth
#define ALSyn                __orig_ALSyn
#define ALEvent              __orig_ALEvent
#define ALEvent_s            __orig_ALEvent_s
#define ALEventListItem      __orig_ALEventListItem
#define ALEventListItem_s    __orig_ALEventListItem_s
#define ALVoiceState_s       __orig_ALVoiceState_s
#define ALVoiceState         __orig_ALVoiceState

#include <stdint.h>
#include <stddef.h>

/* =============================================
   STANDARD N64 TYPES
   Defined before any other includes (like string.h) to ensure
   that if a project header gets pulled in early, it already has 
   access to s32, u32, etc.
   ============================================= */
typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

typedef int8_t   s8;
typedef int16_t  s16;
typedef int32_t  s32;
typedef int64_t  s64;

typedef volatile uint8_t  vu8;
typedef volatile uint16_t vu16;
typedef volatile uint32_t vu32;
typedef volatile uint64_t vu64;

typedef volatile int8_t   vs8;
typedef volatile int16_t  vs16;
typedef volatile int32_t  vs32;
typedef volatile int64_t  vs64;

typedef float  f32;
typedef double f64;

/* =============================================
   C++ <cstring> SHADOWING FIX
   The project has an `include/string.h` which shadows the NDK `<string.h>`.
   When C++ standard library includes <cstring>, it expects all standard 
   C string functions to be declared so it can import them to std::. 
   Because the project's string.h lacks functions like strncat, <cstring> fails.
   We forward declare them here in extern "C" to satisfy libc++.
   ============================================= */
#ifdef __cplusplus
extern "C" {
    void* memchr(const void*, int, size_t);
    int memcmp(const void*, const void*, size_t);
    void* memcpy(void*, const void*, size_t);
    void* memmove(void*, const void*, size_t);
    void* memset(void*, int, size_t);
    char* strcat(char*, const char*);
    char* strchr(const char*, int);
    int strcmp(const char*, const char*);
    int strcoll(const char*, const char*);
    char* strcpy(char*, const char*);
    size_t strcspn(const char*, const char*);
    char* strerror(int);
    size_t strlen(const char*);
    char* strncat(char*, const char*, size_t);
    int strncmp(const char*, const char*, size_t);
    char* strncpy(char*, const char*, size_t);
    char* strpbrk(const char*, const char*);
    char* strrchr(const char*, int);
    size_t strspn(const char*, const char*);
    char* strstr(const char*, const char*);
    char* strtok(char*, const char*);
    size_t strxfrm(char*, const char*, size_t);

    /* cwchar functions sometimes needed by string headers */
    wchar_t* wmemchr(const wchar_t*, wchar_t, size_t);
    int wmemcmp(const wchar_t*, const wchar_t*, size_t);
    wchar_t* wmemcpy(wchar_t*, const wchar_t*, size_t);
    wchar_t* wmemmove(wchar_t*, const wchar_t*, size_t);
    wchar_t* wmemset(wchar_t*, wchar_t, size_t);
}
#endif

#include <stdlib.h>
#include <stdio.h>
#include <math.h>

/* =============================================
   OS TYPE DEFINITIONS
   os_message.h and os_pi.h are blocked above.
   OSMesg: SDK defines as typedef void* — NOT a struct.
   ============================================= */
#ifndef __BKA_OS_TYPES_DEFINED
#define __BKA_OS_TYPES_DEFINED

typedef void *OSMesg;

typedef struct OSMesgQueue_s {
    s32      validCount;
    s32      first;
    s32      msgCount;
    OSMesg  *msg;
} OSMesgQueue;

typedef struct OSPiHandle_s {
    struct OSPiHandle_s *next;
    u8   type;
    u8   latency;
    u8   pageSize;
    u8   relDuration;
    u8   pulse;
    u8   domain;
    u32  baseAddress;
    u32  speed;
    u32  _pad[3];
} OSPiHandle;

/* OSIoMesg: anonymous struct tag in SDK — match exactly. */
typedef struct {
    OSMesgQueue *hdr;
    void        *dramAddr;
    u32          devAddr;
    u32          size;
    u32          piHandle;
} OSIoMesg;

#endif /* __BKA_OS_TYPES_DEFINED */

/* =============================================
   BOOLEAN / STANDARD MACROS
   ============================================= */
#ifndef TRUE
#define TRUE 1
#endif

#ifndef FALSE
#define FALSE 0
#endif

#ifndef NULL
#define NULL 0
#endif

/* =============================================
   n64_bool and n64_* convenience macros
   ============================================= */
#ifndef BKA_SANITIZER_SUPPORT_DEFINED
#define BKA_SANITIZER_SUPPORT_DEFINED

typedef s32 n64_bool;

#ifndef n64_malloc
#define n64_malloc  malloc
#define n64_free    free
#define n64_realloc realloc
#define n64_calloc  calloc
#define n64_printf  printf
#define n64_sprintf sprintf
#define n64_memcpy  memcpy
#define n64_memmove memmove
#define n64_strlen  strlen
#define n64_strcpy  strcpy
#define n64_strcat  strcat
#define n64_sin     sin
#define n64_cos     cos
#endif
#endif

/* =============================================
   CONSTANTS
   ============================================= */
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#ifndef G_TRI2
#define G_TRI2 0xb1
#endif

#ifndef G_QUAD
#define G_QUAD 0xb5
#endif

/* =============================================
   ALGlobals COMPILER FIX
   otr_builder.cpp fails because it casts a pointer to ALGlobals*
   without including libaudio.h. Since ALGlobals is an anonymous 
   struct typedef in the SDK, we cannot safely forward-declare it 
   in C++ without causing redefinition conflicts in NativeBridge.cpp.
   Instead, we eager-load the header here so the definition is 
   globally available.
   ============================================= */
#if __has_include(<PR/libaudio.h>)
#include <PR/libaudio.h>
#elif __has_include(<libaudio.h>)
#include <libaudio.h>
#endif

#endif /* BKA_ANDROID_N64_TYPES_H */
