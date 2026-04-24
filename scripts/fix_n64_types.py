import os

def fix_n64_types():
    types_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    headers_to_wipe = [
        'include/2.0L/PR/libaudio.h',
        'include/2.0L/PR/n_libaudio.h',
        'include/2.0L/PR/os.h',
        'include/2.0L/PR/gu.h',
        'include/2.0L/PR/gbi.h',
        'include/n_synth.h',
        'include/synthInternals.h'
    ]

    print("Step 1: Maintaining silenced SDK headers...")
    for header in headers_to_wipe:
        if os.path.exists(header):
            with open(header, 'w') as f:
                f.write("// Silenced by fix_n64_types.py to prevent redeclaration conflicts\n")

    print(f"\nStep 2: Injecting Complete Audio Synthesis types into {types_path}...")
    content = """#ifndef _BKA_ANDROID_N64_TYPES_H_
#define _BKA_ANDROID_N64_TYPES_H_

#include <stdint.h>
#include <stddef.h>
#include <math.h>

// --- BASIC TYPES ---
typedef uint8_t   u8;
typedef int8_t    s8;
typedef uint16_t  u16;
typedef int16_t   s16;
typedef uint32_t  u32;
typedef int32_t   s32;
typedef uint64_t  u64;
typedef int64_t   s64;
typedef float     f32;
typedef double    f64;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

// --- MATH & MATRIX TYPES ---
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct {
    int32_t m[4][4];
} Mtx;

// --- OS TYPES & INTERRUPTS ---
#define OS_STATE_STOPPED    1
#define OS_STATE_RUNNABLE   2
#define OS_STATE_RUNNING    4
#define OS_STATE_WAITING    8

typedef s32 OSPri;
typedef void* OSMesg;
typedef u32 OSIntMask;

#define OS_IM_NONE          0

typedef struct OSMesgQueue_s {
    u32 valid;
    u32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    struct OSThread_s **queue;
    struct OSThread_s *tnext;
    u16 state;
    u16 flags;
    s32 id;
    int fp;
} OSThread;

// --- AUDIO BASE TYPES ---
typedef s32 ALMicroTime;
typedef s32 ALPan;
typedef uint64_t Acmd;

typedef struct {
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

// --- FILTER SYSTEM ---
typedef s32 (*ALCmdHandler)(void *, s16 *, s32, s32, void *);
typedef s32 (*ALSetParam)(void *, s32, void *);

typedef struct ALFilter_s {
    struct ALFilter_s *source;
    ALCmdHandler      handler;
    ALSetParam        setParam;
    s32               inp;
    s32               outp;
    s32               type;
} ALFilter;

// Filter Type IDs
#define AL_SYN_FILTER       1
#define AL_RESAMPLE_FILTER  2
#define AL_ENV_FILTER       3
#define AL_FX_FILTER        4
#define AL_AUX_FILTER       5

// Parameter IDs
#define AL_FILTER_SET_WAVETABLE     1
#define AL_FILTER_SET_PITCH         2
#define AL_FILTER_SET_UNITY_PITCH   3
#define AL_FILTER_START             4
#define AL_FILTER_STOP              5

// Filter output IDs
#define AL_RESAMPLER_OUT            1

// --- MIXER & ENVELOPE TYPES ---
typedef struct ALParam_s {
    struct ALParam_s    *next;
    s32                 delta;
    s32                 type;
} ALParam;

typedef struct {
    ALFilter            filter;
    ALParam             *ctrlList;
    ALParam             *freeList;
    // Mixer state
    s16                 *outBuf;
    s32                 lptr;
} ALEnvMixer;

// --- LINKED LISTS ---
typedef struct ALLink_s {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

// --- EVENT SYSTEM ---
typedef struct {
    ALLink      node;
    s32         delta;
    union {
        u8      raw[16];
    } evt;
} ALEventListItem;

typedef struct {
    ALLink      freeList;
    ALLink      allocList;
} ALEvtq;

typedef ALEvtq ALEventQueue;

// --- EFFECTS (FX) SYSTEM ---
typedef struct {
    s32         input;
    s32         output;
    s32         fbcoef;
    s32         ffcoef;
    s32         gain;
} ALDelay;

typedef struct {
    s32         maxDelay;
    s32         section_count;
    ALDelay     *delay;
} ALFx;

typedef struct {
    s32         maxVoices;
    s32         maxEvents;
    s32         maxChannels;
    s32         sampleRate;
    void        *params;
} ALSynConfig;

typedef void* (*ALSetFXParam)(void *, s32, void *);

typedef struct {
    ALFilter    filter;
} ALLowPass;

// FX Presets
#define AL_FX_NONE          0
#define AL_FX_SMALLROOM     1
#define AL_FX_BIGROOM       2
#define AL_FX_CHORUS        3
#define AL_FX_FLANGE        4
#define AL_FX_ECHO          5
#define AL_FX_CUSTOM        6

// --- PRE-EXISTING VOICES & SYNTH ---
typedef struct PVoice_s {
    ALFilter    filter;
    struct PVoice_s *next;
    s32         offset;
} PVoice;

typedef struct ALSyn_s {
    PVoice      *pVoiceList;
    s32         paramSamples;
    u32         curSamples;
    u32         maxSamples;
} ALSyn;

typedef struct ALGlobals_s {
    ALSyn *drvr;
    u8    reserved[1024];
} ALGlobals;

// --- EVENT DEFINITIONS ---
typedef struct {
    s32  type;
    union {
        u8          raw[16];
    } msg;
} ALEvent;

// --- EXTERNALS ---
#ifdef __cplusplus
extern "C" {
#endif
extern ALGlobals *alGlobals;
extern ALSyn *n_syn;
extern OSThread *__osRunningThread;

void alFilterNew(ALFilter *f, ALCmdHandler h, ALSetParam s, s32 type);
void alLink(ALLink *ln, ALLink *to);
void alUnlink(ALLink *ln);
void alCopy(void *src, void *dst, s32 size);
OSIntMask osSetIntMask(OSIntMask mask);
void* alHeapAlloc(ALHeap *hp, s32 count, s32 size);

#ifdef __cplusplus
}
#endif

#endif // _BKA_ANDROID_N64_TYPES_H_
"""

    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ Audio Synthesis Engine Types Injected: {types_path}")

if __name__ == '__main__':
    fix_n64_types()
