import os

def fix_n64_types():
    types_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    # Silence the original SDK headers to prevent conflicts
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
                f.write("// Silenced by fix_n64_types.py\n")

    print(f"\nStep 2: Injecting comprehensive N64 and Audio types into {types_path}...")
    content = """#ifndef _BKA_ANDROID_N64_TYPES_H_
#define _BKA_ANDROID_N64_TYPES_H_

#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif

#include <stdint.h>
#include <stddef.h>
#include <math.h>

// --- MATH CONSTANTS ---
#ifndef M_PI
#define M_PI    3.14159265358979323846
#endif
#ifndef M_PI_2
#define M_PI_2  1.57079632679489661923
#endif

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

// --- OS & KERNEL ---
typedef s32  OSPri;
typedef void* OSMesg;
typedef struct { u32 valid; u32 msgCount; OSMesg *msg; } OSMesgQueue;

typedef struct {
    u16     button;
    s8      stick_x;
    s8      stick_y;
    u8      errno;
} OSContPad;

// --- AUDIO TYPES & ENUMS ---
typedef s32 ALMicroTime;
typedef s32 ALPan;

#define AL_FILTER_START_VOICE      1
#define AL_FILTER_SET_WAVE         2
#define AL_FILTER_SET_PAN          3
#define AL_FILTER_SET_VOLUME       4
#define AL_FILTER_SET_PITCH        5
#define AL_FILTER_SET_FXAMT        6
#define AL_FILTER_STOP_VOICE       7
#define AL_FILTER_ADD_UPDATE       8
#define AL_FILTER_START_VOICE_ALT  9

#define ERR_ALSYN_NO_UPDATE        3000

// --- AUDIO STRUCTURES ---
typedef struct {
    struct ALFilter_s *source;
    int32_t (*handler)(void *, int16_t *, int32_t, int32_t, void *);
} ALFilter;

typedef struct PVoice_s {
    ALFilter    filter;
    struct PVoice_s *next;
    s32         offset;
} PVoice;

typedef struct {
    PVoice      *pvoice;
    ALPan       pan;
    u8          volume;
    u8          fxMix;
    f32         pitch;
    f32         unityPitch;
} N_ALVoice;

typedef struct {
    u8          type;
    u32         delta;
    void        *wave;
    void        *next;
    f32         unity;
} ALStartParam;

typedef struct {
    u8          type;
    u32         delta;
    void        *wave;
    void        *next;
    f32         unity;
    ALPan       pan;
    u8          volume;
    u8          fxMix;
    f32         pitch;
    s32         samples;
} ALStartParamAlt;

typedef struct {
    PVoice      *pVoiceList;
    s32         paramSamples;
    u32         curSamples;
    u32         maxSamples;
} ALSyn;

// Placeholder for the global synth instance
extern ALSyn *n_syn;

// --- GFX & VTX ---
typedef uint64_t Gfx;
typedef struct {
    short ob[3]; u16 flag; short tc[2]; u8 cn[4];
} Vtx_t;
typedef union { Vtx_t v; long long force_alignment; } Vtx;

// --- FUNCTION PROTOTYPES ---
#ifdef __cplusplus
extern "C" {
#endif
void* __n_allocParam();
void n_alEnvmixerParam(void *filter, s32 paramID, void *ptr);
s32 _n_timeToSamples(ALMicroTime t);
#define ALFailIf(cond, code) if(cond) return;
#ifdef __cplusplus
}
#endif

#endif // _BKA_ANDROID_N64_TYPES_H_
"""
    
    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ Updated: {types_path}")

if __name__ == '__main__':
    fix_n64_types()
