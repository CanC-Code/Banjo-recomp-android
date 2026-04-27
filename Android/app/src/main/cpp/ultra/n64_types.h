#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H

/* =============================================
   PREPROCESSOR INTERCEPTION
   Neutralize ALL conflicting SDK definitions BEFORE includes
   ============================================= */

/* 1. Neutralize ultratypes.h */
#define _ULTRA64_TYPES_H_ 1
#define _LANGUAGE_C 1
#define _LANGUAGE_C_PLUS_PLUS 1
#define F3DEX_GBI_2 1

/* 2. Neutralize PR/abi.h's Acmd */
#define Acmd BKA_Acmd_Compat

/* 3. Intercept all other conflicting types */
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
   STANDARD N64 TYPES REPLACEMENT (ADDED FIX)
   Map modern standard integer types to legacy N64 types.
   ============================================= */
#include <stdint.h>

/* Unsigned types */
typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

/* Signed types */
typedef int8_t   s8;
typedef int16_t  s16;
typedef int32_t  s32;
typedef int64_t  s64;

/* Volatile Unsigned types */
typedef volatile uint8_t  vu8;
typedef volatile uint16_t vu16;
typedef volatile uint32_t vu32;
typedef volatile uint64_t vu64;

/* Volatile Signed types */
typedef volatile int8_t   vs8;
typedef volatile int16_t  vs16;
typedef volatile int32_t  vs32;
typedef volatile int64_t  vs64;

/* Floating point types */
typedef float  f32;
typedef double f64;

/* =============================================
   SANITIZER & STANDARD LIBS
   ============================================= */
#ifndef BKA_SANITIZER_SUPPORT_DEFINED
#define BKA_SANITIZER_SUPPORT_DEFINED
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>

/* Using the newly defined s32 type! */
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
   ============================================= */
#ifndef BKA_BANJO_LAYER
#define BKA_BANJO_LAYER

typedef struct __orig_ALEventListItem N_ALEventListItem;

#ifdef __cplusplus
extern "C" {
#endif

/* External layer implementations can be defined below */

#ifdef __cplusplus
}
#endif

#endif /* BKA_BANJO_LAYER */

#endif /* BKA_ANDROID_N64_TYPES_H */
