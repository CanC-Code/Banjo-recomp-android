#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H

/* =============================================
   PREPROCESSOR INTERCEPTION
   Neutralize ALL conflicting SDK definitions BEFORE any includes.
   This file is force-included via -include, so these defines fire
   before every TU in the build.
   ============================================= */

/* 1. Block ultratypes.h via every known guard variant */
#define _ULTRA64_TYPES_H_  1
#define _ULTRATYPES_H_     1
#define _PR_ULTRATYPES_H_  1
#define ULTRATYPES_H       1

/* 2. Block include/core2/vla.h pre-emptively.
      Some source files explicitly #include <string.h> (the project-local
      wrapper) which chains: string.h -> structs.h -> core2/vla.h ->
      #include<ultratypes.h> which fails (file not found).
      Defining vla.h's own include guard here stops it from opening at all. */
#define _VLA_H_            1
#define VLA_H              1
#define _CORE2_VLA_H_      1

/* 3. Language / GBI flags */
#define _LANGUAGE_C 1
#define _LANGUAGE_C_PLUS_PLUS 1
#define F3DEX_GBI_2 1

/* 4. Neutralize PR/abi.h's Acmd */
#define Acmd BKA_Acmd_Compat

/* 5. Intercept conflicting AL types — these redirect the SDK's definitions
      to mangled names so our canonical definitions below win.
      NOTE: do NOT use these mangled names in any typedef in this file;
      the real structs aren't defined until the AL headers are pulled in
      by individual source files. */
#define ALLink_s             __orig_ALLink_s
#define ALLink               __orig_ALLink
#define ALVoice_s            __orig_ALVoice_s
#define ALVoice              __orig_ALVoice
#define N_ALVoice_s          __orig_N_ALVoice_s
#define N_ALVoice            __orig_N_ALVoice
#define ALSynth              __orig_ALSynth
#define ALSyn                __orig_ALSyn
#define ALGlobals            __orig_ALGlobals
#define ALGlobals_s          __orig_ALGlobals_s
#define ALEvent              __orig_ALEvent
#define ALEvent_s            __orig_ALEvent_s
#define ALEventListItem      __orig_ALEventListItem
#define ALEventListItem_s    __orig_ALEventListItem_s
#define ALVoiceState_s       __orig_ALVoiceState_s
#define ALVoiceState         __orig_ALVoiceState

/* =============================================
   STANDARD N64 TYPES
   Map modern stdint types to legacy N64 names.
   ============================================= */
#include <stdint.h>
#include <stddef.h>

/* Unsigned */
typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

/* Signed */
typedef int8_t   s8;
typedef int16_t  s16;
typedef int32_t  s32;
typedef int64_t  s64;

/* Volatile Unsigned */
typedef volatile uint8_t  vu8;
typedef volatile uint16_t vu16;
typedef volatile uint32_t vu32;
typedef volatile uint64_t vu64;

/* Volatile Signed */
typedef volatile int8_t   vs8;
typedef volatile int16_t  vs16;
typedef volatile int32_t  vs32;
typedef volatile int64_t  vs64;

/* Floating point */
typedef float  f32;
typedef double f64;

/* =============================================
   OS PI / MESSAGE QUEUE FORWARD DECLARATIONS
   Some emulator files (pi_hle.cpp etc.) use these types directly.
   They are normally provided by ultra64.h / os_pi.h but those headers
   are blocked/unavailable on Android NDK. Forward-declare the structs
   and provide the typedefs so TUs that don't pull in ultra64.h still
   compile.
   ============================================= */
#ifndef __OS_TYPES_DECLARED
#define __OS_TYPES_DECLARED

typedef struct OSMesg_s {
    void *data;
} OSMesg;

typedef struct OSMesgQueue_s {
    /* opaque on Android — real fields not needed by port stubs */
    s32      validCount;
    s32      first;
    s32      msgCount;
    OSMesg  *msg;
} OSMesgQueue;

typedef struct OSIoMesg_s {
    /* PI DMA message */
    OSMesgQueue *hdr;
    void        *dramAddr;
    u32          devAddr;
    u32          size;
    u32          piHandle;
} OSIoMesg;

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
    /* pad to match SDK struct size */
    u32  _pad[3];
} OSPiHandle;

#endif /* __OS_TYPES_DECLARED */

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
   STANDARD LIBS
   Do NOT include the project-local include/string.h here —
   that wrapper chains into core2/vla.h -> ultratypes.h (missing).
   The system <string.h> is already covered by <stdlib.h> below,
   and vla.h is pre-empted by its guard defines above for any TU
   that pulls it in directly.
   ============================================= */
#ifndef BKA_SANITIZER_SUPPORT_DEFINED
#define BKA_SANITIZER_SUPPORT_DEFINED
#include <stdlib.h>
#include <stdio.h>
#include <math.h>

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
   BANJO COMPAT LAYER
   N_ALEventListItem typedef is intentionally removed from here.
   ALEventListItem is macro-redirected to __orig_ALEventListItem above,
   so typedef-ing it here produces "unknown type name '__orig_ALEventListItem'"
   because the real struct definition hasn't been seen yet at forced-include
   time. The typedef must live in a file that includes the AL headers first.
   ============================================= */

#endif /* BKA_ANDROID_N64_TYPES_H */
