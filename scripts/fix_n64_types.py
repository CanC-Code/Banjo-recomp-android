import os

def fix_n64_types():
    """
    Generates a master n64_types.h that harmonizes Android custom types
    with the original N64 SDK headers via preprocessor interception.
    """
    types_path = "Android/app/src/main/cpp/ultra/n64_types.h"

    content = """#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H

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
#include "PR/libaudio.h"

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
} ALPVoice;

typedef ALPVoice PVoice;
typedef ALPVoice N_PVoice;

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
    void *handler;
    void *setParam;
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

#endif
"""

    os.makedirs(os.path.dirname(types_path), exist_ok=True)

    with open(types_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ n64_types.h generated (harmonized SDK version with SGI macros)")

if __name__ == "__main__":
    fix_n64_types()
