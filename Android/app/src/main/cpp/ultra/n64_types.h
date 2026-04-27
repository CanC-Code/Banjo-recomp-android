#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H

/* =============================================
   PREPROCESSOR INTERCEPTION
   Force-included via -include before every TU.
   All blocking defines must fire before any #include below.
   ============================================= */

/* --- Block ultratypes.h (all known guard variants) --- */
#define _ULTRA64_TYPES_H_  1
#define _ULTRATYPES_H_     1
#define _PR_ULTRATYPES_H_  1
#define ULTRATYPES_H       1

/* --- Block core2/vla.h (all known guard variants) ---
   Some TUs reach this via:
     <cstring> -> include/string.h -> structs.h -> core2/vla.h
   vla.h does a bare #include<ultratypes.h> with no guard on the include
   itself, so we must prevent the file from opening at all. */
#define _VLA_H_            1
#define VLA_H              1
#define _CORE2_VLA_H_      1
#define CORE2_VLA_H        1
#define _BKA_VLA_GUARD_    1

/* --- Block os_message.h and os_pi.h ---
   We previously forward-declared OSMesg/OSMesgQueue/OSIoMesg/OSPiHandle
   as structs, but the real SDK headers define:
     os_message.h: typedef void* OSMesg  (NOT a struct)
   This caused hard type-mismatch redefinitions. The cleanest fix is to
   block os_message.h and os_pi.h entirely and provide our own compatible
   minimal definitions below (matching the SDK's actual types). */
#define _OS_MESSAGE_H_     1
#define _OS_PI_H_          1
#define _PR_OS_MESSAGE_H_  1
#define _PR_OS_PI_H_       1

/* --- Language / GBI flags --- */
#define _LANGUAGE_C            1
#define _LANGUAGE_C_PLUS_PLUS  1
#define F3DEX_GBI_2            1

/* --- Block PR/abi.h's Acmd --- */
#define Acmd BKA_Acmd_Compat

/* --- Intercept conflicting AL types ---
   These redirect the SDK's struct/typedef definitions to mangled names.
   IMPORTANT: Only redirect types that are purely SDK-internal and never
   used as a bare type name in project source files. Types used directly
   in source (like ALGlobals) must NOT be redirected here — those TUs
   need the real definition from the AL headers they include themselves. */
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
/* ALGlobals and ALGlobals_s intentionally NOT redirected:
   emulator/stubs.cpp uses ALGlobals* as a real type. */

/* =============================================
   STANDARD N64 TYPES
   ============================================= */
#include <stdint.h>
#include <stddef.h>

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
   OS TYPE DEFINITIONS
   Provided here because os_message.h and os_pi.h are blocked above.
   These MUST exactly match the SDK's own definitions to avoid
   redefinition errors if the blocking guards ever miss a path.

   os_message.h:52: typedef void* OSMesg          (NOT a struct)
   os_message.h:57: typedef struct OSMesgQueue_s   { s32 validCount; s32 first; s32 msgCount; void* msg; }
   os_pi.h:80:      typedef struct OSPiHandle_s    { ... }
   os_pi.h:116:     typedef struct OSIoMesg_s { ... } OSIoMesg
   ============================================= */
#ifndef __BKA_OS_TYPES_DEFINED
#define __BKA_OS_TYPES_DEFINED

/* OSMesg: the SDK defines this as void*, not a struct. Match exactly. */
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

/* OSIoMesg: the SDK struct tag is plain 'OSIoMesg' (anonymous tag),
   not 'OSIoMesg_s'. Match to avoid tag-mismatch redefinition. */
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
   STANDARD LIBS
   Do NOT include the project-local include/string.h — it chains into
   structs.h -> core2/vla.h -> #include<ultratypes.h> (missing file).
   core2/vla.h is also pre-empted by its guard defines above for any TU
   that pulls it in via C++ stdlib headers (cstring -> string.h -> ...).
   System <string.h> is already provided by <stdlib.h> below.
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

#endif /* BKA_ANDROID_N64_TYPES_H */
