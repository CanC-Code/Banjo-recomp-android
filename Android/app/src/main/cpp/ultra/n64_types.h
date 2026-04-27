#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H


/* =========================
   FUNDAMENTAL TYPES
   ========================= */
typedef unsigned char      u8;
typedef signed char        s8;
typedef unsigned short     u16;
typedef signed short       s16;
typedef unsigned int       u32;
typedef signed int         s32;
typedef unsigned long long u64;
typedef signed long long   s64;
typedef float              f32;
typedef double             f64;


/* =========================
   ACMD OVERRIDE (for PR/abi.h compatibility)
   ========================= */
#ifndef BKA_ACMD_OVERRIDE
#define BKA_ACMD_OVERRIDE

/* Neutralize PR/abi.h's typedef by defining Acmd as a macro */
#define Acmd BKA_Acmd_Neutralized

/* Define Acmd as a struct */
typedef struct BKA_Acmd_Neutralized {
    u32 w0;
    u32 w1;
} BKA_Acmd_Neutralized;

/* Redefine aClearBuffer to work with Acmd as a struct */
#undef aClearBuffer
#define aClearBuffer(_a, _d, _c) \
    (_a)->w0 = _SHIFTL(A_CLEARBUFF, 24, 8) | _SHIFTL((_d), 0, 24), \
    (_a)->w1 = (unsigned int)(_c)

/* Define Acmd as the struct for our code */
#define Acmd BKA_Acmd_Neutralized
#endif



/* --- HARMONIZER_V21_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

/*
 * ALParam — full sequencer parameter struct.
 * Required by synthInternals.h and n_synth.h.
 */
#ifndef BKA_ALPARAM_DEFINED
#define BKA_ALPARAM_DEFINED
typedef struct ALParam_s {
    struct ALParam_s   *next;
    s32                 delta;
    s16                 type;
    s32                 samples;
    f32                 pitch;
    s16                 unity;
    u8                  pan;
    u8                  volume;
    u8                  fxMix;
    void               *wave;
    union { f32 f; s32 i; } data;
} ALParam;

typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;
#endif /* BKA_ALPARAM_DEFINED */

/*
 * ALCmdHandler — required by synthInternals.h:92.
 * Updated to return Acmd* and take 5 arguments to match auxbus.c usage.
 * ALSetParam   — required by synthInternals.h:92 and n_synth.h:130.
 */
#ifndef BKA_ALHANDLERS_DEFINED
#define BKA_ALHANDLERS_DEFINED
typedef struct BKA_Acmd_Neutralized *(*ALCmdHandler)(void *, s16 *, s32, s32, void *);  // Returns Acmd* and takes 5 args
typedef s32  (*ALSetParam)(void *, s32, void *);
#endif /* BKA_ALHANDLERS_DEFINED */

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
/*
 * CLEAN, HARMONIZED N64 TYPE FOUNDATION
 * - Protects against libaudio/gu struct collisions
 * - Delegates Banjo-specific structs (ALSynth/ALGlobals) to sister scripts
 */

#include <stdint.h>
#include <stddef.h>

/* =========================
   FUNDAMENTAL TYPES
   ========================= */
typedef unsigned char      u8;
typedef signed char        s8;
typedef unsigned short     u16;
typedef signed short       s16;
typedef unsigned int       u32;
typedef signed int         s32;
typedef unsigned long long u64;
typedef signed long long   s64;
typedef float              f32;
typedef double             f64;

/* =========================
   PREPROCESSOR SDK INTERCEPTION
   ========================= */
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
#define ALSeqMarker          __orig_ALSeqMarker
#define ALCSeqMarker         __orig_ALCSeqMarker
#define ADPCM_STATE          __orig_ADPCM_STATE

/* Intercept macro enums that sister scripts inject as #defines */
#define AL_SEQP_LOOP_EVT     __orig_AL_SEQP_LOOP_EVT
#define AL_MIDI_FX_CTRL_0    __orig_AL_MIDI_FX_CTRL_0
#define AL_MIDI_FX_CTRL_1    __orig_AL_MIDI_FX_CTRL_1
#define AL_MIDI_FX_CTRL_2    __orig_AL_MIDI_FX_CTRL_2
#define AL_MIDI_FX_CTRL_3    __orig_AL_MIDI_FX_CTRL_3

/* * ENABLE LEGACY SGI TYPEDEFS
 * The N64 SDK hides Gfx, Mtx, and LookAt structs behind these legacy macros.
 * We must explicitly define them so PR/gbi.h exposes the types to Clang C++.
 */
#define _LANGUAGE_C 1
#define _LANGUAGE_C_PLUS_PLUS 1
#define F3DEX_GBI_2 1

/* * Force include the N64 SDK headers NOW. */
#include "PR/ultratypes.h"
#include "PR/os.h"
#include "PR/gbi.h"
#include "PR/gu.h"
#ifndef PR_ABI_H_INCLUDED
#define PR_ABI_H_INCLUDED
#include "PR/libaudio.h"
#endif

/* =========================
   RESTORE NAMESPACE
   ========================= */
#undef ALLink_s
#undef ALLink
#undef ALVoice_s
#undef ALVoice
#undef N_ALVoice_s
#undef N_ALVoice
#undef ALSynth
#undef ALSyn
#undef ALGlobals
#undef ALGlobals_s
#undef ALEvent
#undef ALEvent_s
#undef ALEventListItem
#undef ALEventListItem_s
#undef ALVoiceState_s
#undef ALVoiceState
#undef ALSeqMarker
#undef ALCSeqMarker
#undef ADPCM_STATE

#undef AL_SEQP_LOOP_EVT
#undef AL_MIDI_FX_CTRL_0
#undef AL_MIDI_FX_CTRL_1
#undef AL_MIDI_FX_CTRL_2
#undef AL_MIDI_FX_CTRL_3

/* =========================
   CUSTOM ANDROID/BANJO PRIMITIVES
   ========================= */
typedef u64 Acmd;

typedef struct ALLink_s {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

typedef s32 ALMicroTime;

struct N_ALVoice_s;

typedef struct ALPVoice_s {
    ALLink node;
    struct N_ALVoice_s *vvoice;
    s32                 offset;       /* sample offset into wave */} ALPVoice;

typedef ALPVoice PVoice;
struct ALEvent_s {
    s32 type;
    union {
        struct {
            struct N_ALVoice_s *voice;
            u8 chan;
        } note;
        u8 raw[32];
    } msg;
};
typedef struct ALEvent_s ALEvent;
typedef ALEvent N_ALEvent;

typedef struct ALEventListItem_s {
    ALLink      node;
    ALMicroTime delta;
    ALEvent     *evt;
} ALEventListItem;

typedef struct N_ALVoice_s {
    struct N_ALVoice_s *next;
    ALPVoice *pvoice;
    void *clientPrivate;
    s16 unityPitch;
} N_ALVoice;

typedef N_ALVoice ALVoice;

typedef struct ALVoiceState_s {
    struct ALVoiceState_s *next;
    ALVoice *voice;
    f32 pitch;
    u8 state;
} ALVoiceState;
typedef ALVoiceState N_ALVoiceState;

typedef struct ALFilter_s {
    struct ALFilter_s *source;
    struct BKA_Acmd_Neutralized *(*handler)(void *, s16 *, s32, s32, void *);
    ALSetParam setParam;
    s32 inp;
    s32 outp;
    s32 type;
} ALFilter;

/*
 * DELEGATION NOTICE:
 * ALSynth and ALGlobals stubs have been REMOVED from this core file.
 */

#ifdef __cplusplus
extern "C" {
#endif

/* Safely forward declare the global pointer */
struct ALGlobals_s;
extern struct ALGlobals_s *alGlobals;

#ifdef __cplusplus
}
#endif


/* =========================
   BKA BANJO COMPAT LAYER
   (HARMONIZED WITH SDK)
   ========================= */
#ifndef BKA_BANJO_LAYER
#define BKA_BANJO_LAYER

/* --- Safe typedef aliases --- */
typedef ALEventListItem N_ALEventListItem;

/* * NOTE: 
 * - AL_SEQP_LOOP_EVT and AL_MIDI_FX_CTRL constants removed. 
 * They are natively provided by the PR/libaudio.h enums now.
 * - ALCSeqMarker alias removed to prevent 'unknown type' and 
 * typedef redefinition conflicts with the N64 SDK.
 */

/* --- SAFE forward-only prototypes (no signature conflicts) --- */
#ifdef __cplusplus
extern "C" {
#endif

/* Use void* to avoid ABI mismatch */
extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alResamplePull(void *, s16 *, Acmd *);
extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);
extern Acmd *n_alSavePull(s32, Acmd *);
extern Acmd *n_alAuxBusPull(void);
extern Acmd *n_alFxPull(void);
extern Acmd *n_alMainBusPull(void);

#ifdef __cplusplus
}
#endif

#endif /* BKA_BANJO_LAYER */


#ifndef BKA_SANITIZER_SUPPORT_DEFINED
#define BKA_SANITIZER_SUPPORT_DEFINED

/* BKA SANITIZER SUPPORT */
/* Inject required standard headers so expanded macros don't cause 'undeclared identifier' errors in C++17 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
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

#endif /* BKA_SANITIZER_SUPPORT_DEFINED */


/* =========================
   BANJO-SPECIFIC AUDIO STRUCTS
   ========================= */
#ifndef BKA_ALSYNTH_DEFINED
#define BKA_ALSYNTH_DEFINED
typedef struct ALSynth_s { u8 opaque_pad[256]; } ALSynth;
typedef ALSynth ALSyn; /* Fulfill legacy SDK alias requirements */
#endif

#ifndef BKA_ALGLOBALS_DEFINED
#define BKA_ALGLOBALS_DEFINED
typedef struct ALGlobals_s {
    ALSynth drvr;
    u8 pad[2048];
} ALGlobals;
#endif


/* =========================
   MATH CONSTANTS
   ========================= */
#ifndef BKA_OSPRI_DEFINED
#define BKA_OSPRI_DEFINED

/* NOTE: OSPri is natively provided by PR/os.h via our master include list, 
 * so the manual typedef has been removed to prevent Clang redefinition errors.
 */

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#endif /* BKA_OSPRI_DEFINED */


/* =========================
   RECOMPILATION OPCODE EXTENSIONS
   ========================= */
#ifndef BKA_MISSING_MACROS_DEFINED
#define BKA_MISSING_MACROS_DEFINED

#ifndef G_TRI2
    #define G_TRI2 0xb1
#endif

#ifndef G_QUAD
    #define G_QUAD 0xb5
#endif

#endif /* BKA_MISSING_MACROS_DEFINED */

#endif
