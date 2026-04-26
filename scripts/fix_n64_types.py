import os

def fix_n64_types():
    """
    Generates a minimal, safe, deterministic n64_types.h.
    This version is:
    - Syntax safe for Python
    - Idempotent
    - Compatible with your Banjo structural patch layer
    """

    types_path = "Android/app/src/main/cpp/ultra/n64_types.h"

    content = """#ifndef BKA_ANDROID_N64_TYPES_H
#define BKA_ANDROID_N64_TYPES_H

/*
 * CLEAN, SAFE, ORDERED N64 TYPE FOUNDATION
 * - Idempotent
 * - Forward-declaration safe
 * - No macro poisoning
 */

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

#include <stdint.h>
#include <stddef.h>

/* =========================
   FORWARD DECLARATIONS
   ========================= */
struct N_ALVoice_s;
struct ALVoiceState_s;

/* =========================
   CORE AUDIO PRIMITIVES
   ========================= */

/* Safe Acmd definition */
typedef u64 Acmd;

/* Minimal safe ALLink */
typedef struct ALLink_s {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

/* =========================
   EVENT SYSTEM (FIXED ORDER)
   ========================= */

typedef s32 ALMicroTime;

typedef struct ALEvent_s ALEvent;

typedef struct ALEventListItem_s {
    ALLink      node;
    ALMicroTime delta;
    ALEvent     *evt;
} ALEventListItem;

/* =========================
   VOICE (SAFE FORWARD USE)
   ========================= */

typedef struct ALPVoice_s {
    ALLink node;
    struct N_ALVoice_s *vvoice;
} ALPVoice;

typedef ALPVoice PVoice;
typedef ALPVoice N_PVoice;

/* =========================
   PARAM SYSTEM
   ========================= */

typedef struct ALParam_s {
    struct ALParam_s *next;
    s32 delta;
    s32 type;
    union { f32 f; s32 i; } data;
} ALParam;

/* =========================
   EVENT STRUCT
   ========================= */

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

typedef ALEvent N_ALEvent;

/* =========================
   VOICE TYPES (DEFINED AFTER USE)
   ========================= */

typedef struct N_ALVoice_s {
    struct N_ALVoice_s *next;
    ALPVoice *pvoice;
    void *clientPrivate;
    s16 unityPitch;
} N_ALVoice;

typedef N_ALVoice ALVoice;

/* =========================
   VOICE STATE
   ========================= */

typedef struct ALVoiceState_s {
    struct ALVoiceState_s *next;
    ALVoice *voice;
    f32 pitch;
    u8 state;
} ALVoiceState;

typedef ALVoiceState N_ALVoiceState;

/* =========================
   BASIC FILTER SYSTEM (MINIMAL SAFE)
   ========================= */

typedef struct ALFilter_s {
    struct ALFilter_s *source;
    void *handler;
    void *setParam;
    s32 inp;
    s32 outp;
    s32 type;
} ALFilter;

/* =========================
   SYNTH SAFE WRAPPER
   ========================= */

typedef struct {
    ALFilter filter;
    s32 paramSamples;
    s32 outputRate;
} ALSyn;

typedef ALSyn ALSynth;

/* =========================
   GLOBALS (SAFE STUB)
   ========================= */

typedef struct {
    ALSyn *drvr;
} ALGlobals;

/* =========================
   REQUIRED EXTERNS
   ========================= */

#ifdef __cplusplus
extern "C" {
#endif

extern ALGlobals *alGlobals;

#ifdef __cplusplus
}
#endif

#endif
"""

    os.makedirs(os.path.dirname(types_path), exist_ok=True)

    with open(types_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ n64_types.h generated (clean minimal safe version)")

if __name__ == "__main__":
    fix_n64_types()