import os

def fix_n64_types():
    types_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    # Headers to wipe to prevent duplicate definition conflicts
    headers_to_wipe = [
        'include/2.0L/PR/libaudio.h',
        'include/2.0L/PR/n_libaudio.h',
        'include/2.0L/PR/os.h',
        'include/2.0L/PR/gu.h',
        'include/2.0L/PR/gbi.h',
        'include/n_synth.h',
        'include/synthInternals.h'
    ]

    print("Step 1: Keeping SDK headers zeroed...")
    for header in headers_to_wipe:
        if os.path.exists(header):
            with open(header, 'w') as f:
                f.write("// Silenced by fix_n64_types.py to prevent redefinition conflicts\n")
            print(f"  ✅ {header}")

    print(f"\nStep 2: Deploying the Master Types Header...")
    content = """#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>
#include <math.h>

// --- MATH & CONSTANTS ---
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif
#ifndef NULL
#define NULL 0
#endif

// --- BASIC N64 TYPES ---
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

typedef volatile uint8_t   vu8;
typedef volatile int8_t    vs8;
typedef volatile uint16_t  vu16;
typedef volatile int16_t   vs16;
typedef volatile uint32_t  vu32;
typedef volatile int32_t   vs32;

// --- OS / KERNEL TYPES ---
typedef s32  OSPri;
typedef void* OSMesg;

typedef struct {
    u32 valid;
    u32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct {
    OSMesg      hdr;
    u32         devAddr;
    void        *dramAddr;
    u32         size;
    OSMesgQueue *retQueue;
} OSIoMesg;

typedef struct { u8 data[32]; }   OSContPad;
typedef struct { u32 type; u32 baseAddr; u8 extra[32]; } OSPiHandle;
typedef struct { u8 data[128]; }  OSTask;
typedef struct { u8 data[4096]; } OSThread;

// --- GRAPHICS TYPES ---
typedef uint64_t Gfx;
typedef uint64_t Acmd;
typedef int32_t  Mtx_t[4][4];
typedef struct { Mtx_t m; } Mtx;
typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef union { Vtx_t v; long long int force_alignment; } Vtx;
typedef struct { short vscale[4]; short vtrans[4]; } Vp_t;
typedef union { Vp_t v; long long int force_alignment; } Vp;

typedef struct { u8 data[64]; }  LookAt;
typedef struct { u8 data[64]; }  Hilite;
typedef struct { u8 data[32]; }  Light;
typedef struct { u8 data[64]; }  PositionalLight;
typedef struct { u8 data[128]; } uSprite;

// --- AUDIO TYPES ---
typedef s32 ALMicroTime;
typedef s32 ALPan;

typedef struct { u32 data[4]; } ALWaveTable;
typedef struct { u32 offset; }  ALVoice;

typedef struct {
    ALVoice *pvoice;
    f32     unityPitch;
} N_ALVoice;

typedef struct ALParam_s {
    struct ALParam_s *next;
    s32              delta;
    u32              type;
    union {
        ALWaveTable *wave;
        void        *ptr;
    };
    f32              unity;
} ALStartParam;

typedef struct {
    struct ALParam_s *next;
    s32              delta;
    u32              type;
    f32              unity;
    ALPan            pan;
    s16              volume;
    u8               fxMix;
} ALStartParamAlt;

typedef struct { s32 paramSamples; } ALSyn;

// Master Globals/Heaps for NativeBridge and structs.h
typedef struct { u8 data[1024]; } ALGlobals;
typedef struct { u8 data[64]; }   ALHeap;
typedef struct { u8 data[64]; }   ALBank;
typedef struct { u8 data[64]; }   ALBankFile;
typedef struct { u8 data[64]; }   ALSeq;
typedef struct { u8 data[64]; }   ALSeqPlayer;
typedef struct { u8 data[128]; }  ALSeqpConfig;
typedef struct { s16 data[16]; }  ADPCM_STATE;

extern ALSyn     *n_syn;
extern ALGlobals *alGlobals;

// Constants & Macros
#define AL_FILTER_START_VOICE     1
#define AL_FILTER_START_VOICE_ALT 2
#define AL_FILTER_ADD_UPDATE      3
#define ERR_ALSYN_NO_UPDATE       0
#define ALFailIf(cond, err)       if(cond) return

#endif // N64_TYPES_H
"""
    
    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ Master types successfully deployed to {types_path}")

if __name__ == '__main__':
    fix_n64_types()
