import os

def fix_n64_types():
    filepath = 'Android/app/src/main/cpp/ultra/n64_types.h'
    print(f"🔊 Hardening the Audio Silencer in {filepath}...")
    
    content = """#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>
#include <math.h>

// --- Math Constants ---
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#ifndef M_PI_F
#define M_PI_F 3.14159265358979323846f
#endif

// Basic N64 Fixed-Width Types
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
typedef volatile uint64_t  vu64;
typedef volatile int64_t   vs64;

// --- Graphics & GBI Primitives ---
typedef uint64_t Acmd;
typedef uint64_t Gfx;
typedef int32_t  Mtx_t[4][4];
typedef struct Mtx { Mtx_t m; } Mtx;

typedef struct Vtx_t {
    short           ob[3];
    unsigned short  flag;
    short           tc[2];
    unsigned char   cn[4];
} Vtx_t;

typedef union Vtx {
    Vtx_t          v;
    long long int  force_structure_alignment;
} Vtx;

// --- SDK SILENCING: THE MEGA-LIST ---
// Audio Guards
#define _LIBAUDIO_H_
#define __LIBAUDIO_H__
#define _N_LIBAUDIO_H_
#define __N_LIBAUDIO_H__
#define _PR_N_LIBAUDIO_H_
#define __PR_N_LIBAUDIO_H__
#define _LIB_AUDIO_H_
#define __LIB_AUDIO_H__
#define _AL_H_
#define __AL_H__

// Graphics & OS Guards
#define _GU_H_
#define __GU_H__
#define _GBI_H_
#define __GBI_H__
#define _IMAGE_H_
#define __IMAGE_H__
#define _OS_H_
#define __OS_H__
#define _ULTRA64_H_
#define __ULTRA64_H__
#define _OSTASK_H_
#define __OSTASK_H__
#define _SPRITE_H_
#define __SPRITE_H__

// --- Our Custom Dummy Definitions ---
// Audio Globals & Heaps
typedef struct { u8 data[1024]; } ALGlobals;
typedef struct { u8 data[64]; }   ALHeap;
typedef struct { u8 data[64]; }   ALBank;
typedef struct { u8 data[64]; }   ALBankFile;
typedef struct { u8 data[64]; }   ALSeq;
typedef struct { u8 data[64]; }   ALSeqPlayer;
typedef struct { u8 data[128]; }  ALSeqpConfig;
typedef struct { s16 data[16]; }  ADPCM_STATE;

// Missing Synth Internal States
typedef struct { u8 data[128]; }  RESAMPLE_STATE;
typedef struct { u8 data[128]; }  ENVMIX_STATE;
typedef struct { u8 data[128]; }  POLEF_STATE;
typedef struct { u8 data[128]; }  FILTER_STATE;

// Graphics / Other
typedef struct { u8 data[128]; } Image;
typedef struct { u8 data[32]; }  Light;
typedef struct { u8 data[64]; }  PositionalLight;
typedef struct { u8 data[64]; }  LookAt;
typedef struct { u8 data[64]; }  Hilite;
typedef struct { u8 data[128]; } OSTask;
typedef struct { u8 data[64]; }  uSprite;

// --- OS / Kernel Types ---
typedef s32 OSPri;
typedef void* OSMesg;

typedef struct OSContPad {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;

typedef struct OSMesgQueue {
    u32 valid;
    u32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct OSIoMesg {
    OSMesg      hdr;
    u32         devAddr;
    void        *dramAddr;
    u32         size;
    struct OSMesgQueue *retQueue;
} OSIoMesg;

typedef struct OSPiHandle {
    u32 type, baseAddr, latency, pulse, pageSize, relDuration;
} OSPiHandle;

typedef struct OSThread {
    u8 data[4096];
} OSThread;

// Boolean definitions
#ifndef N64_BOOL_DEFINED
#define N64_BOOL_DEFINED
typedef int n64_bool;
#define TRUE  1
#define FALSE 0
#endif

#endif // N64_TYPES_H
"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("✅ n64_types.h updated for the Audio Boss!")

if __name__ == '__main__':
    fix_n64_types()
