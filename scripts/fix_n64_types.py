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

    print("Step 1: Keeping SDK headers zeroed...")
    for header in headers_to_wipe:
        if os.path.exists(header):
            with open(header, 'w') as f:
                f.write("// Silenced by fix_n64_types.py\n")
            print(f"  ✅ {header}")

    print(f"\nStep 2: Injecting Corrected Types into {types_path}...")
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

// --- OS / KERNEL / HARDWARE TYPES ---
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

typedef struct {
    u32 type;
    u32 baseAddr;
    u8  latency;
    u8  pulse;
    u8  pageSize;
    u8  relDuration;
} OSPiHandle;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri             priority;
    struct OSThread_s **queue;
    struct OSThread_s *tnext;
    u16               state;
    u16               flags;
    s32               id;
    int               fp;
} OSThread;

typedef struct { u8 data[32]; }   OSContPad;
typedef struct { u8 data[128]; }  OSTask;

// --- GRAPHICS TYPES ---
typedef uint64_t Gfx;
typedef uint64_t Acmd;
typedef struct { int32_t m[4][4]; } Mtx;
typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx;
typedef struct { short vscale[4]; short vtrans[4]; } Vp;

// --- AUDIO TYPES (ASSETS) ---
typedef s32 ALMicroTime;
typedef s32 ALPan;

typedef struct { u32 order; u32 npredictors; s16 book[1]; } ALADPCMBook;
typedef struct { u32 start; u32 end; u32 count; s16 state[16]; } ALADPCMloop;

typedef struct {
    ALADPCMloop     *loop;
    ALADPCMBook     *book;
} ALADPCMWaveInfo;

typedef union {
    ALADPCMWaveInfo adpcmWave;
    struct { u32 u; } rawWave;
} ALWaveInfo;

typedef struct {
    u8              *base;
    s32             len;
    u8              type;
    u8              flags;
    ALWaveInfo      waveInfo;
} ALWaveTable;

typedef struct { ALWaveTable *wavetable; u8 priority; } ALSound;
// FIXED: Added u8 type specifier to soundCount
typedef struct { u8 volume; u8 pan; u8 priority; u8 soundCount; ALSound *sounds[1]; } ALInstrument;
typedef struct { s16 instCount; ALInstrument *instArray[1]; } ALBank;
typedef struct { s16 revision; s16 bankCount; ALBank *bankArray[1]; } ALBankFile;
typedef struct { s16 seqCount; u8 *data; } ALSeqFile;

// --- AUDIO TYPES (ENGINE) ---
typedef struct { u8 data[1024]; } ALGlobals;
typedef struct { 
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

typedef struct { s32 paramSamples; } ALSyn;
typedef struct { u16 type; u8 msg[16]; } ALEvent;
typedef struct { u8 data[128]; } ALEvtQueue;
typedef struct { ALEvtQueue evtq; } ALCSPlayer;

typedef struct {
    u32 offset;
} ALVoice;

typedef struct {
    ALVoice *pvoice;
    f32 unityPitch;
} N_ALVoice;

typedef struct ALFilter_s {
    struct ALFilter_s   *source;
    s32                 (*handler)(void *, s32 *, s32, s32, s32);
    s32                 (*setParam)(void *, s32, void *);
} ALFilter;

// Parameter Packets
typedef struct { void *next; s32 delta; u32 type; ALWaveTable *wave; f32 unity; } ALStartParam;
typedef struct { void *next; s32 delta; u32 type; ALWaveTable *wave; f32 pitch; f32 unity; s16 volume; ALPan pan; u8 fxMix; s32 samples; } ALStartParamAlt;

// --- CROSS-LANGUAGE SYMBOLS ---
#ifdef __cplusplus
extern "C" {
#endif

extern ALGlobals *alGlobals;
extern ALSyn     *n_syn;

void alSeqFileNew(ALSeqFile *file, u8 *base);
void n_alEnvmixerParam(ALVoice *v, s32 p, void *ptr);
void* __n_allocParam(void);
s32 _n_timeToSamples(ALMicroTime t);
void aClearBuffer(u32 ptr, u32 addr, u32 count);

#ifdef __cplusplus
}
#endif

// Audio Macros
#define AL_FILTER_START_VOICE     1
#define AL_FILTER_START_VOICE_ALT 2
#define AL_FILTER_ADD_UPDATE      3
#define AL_FILTER_ADD_SOURCE      4
#define ERR_ALSYN_NO_UPDATE       0
#define ALFailIf(cond, err)       if(cond) return

#endif // N64_TYPES_H
"""
    
    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ Created: {types_path}")

if __name__ == '__main__':
    fix_n64_types()
