import os

def fix_n64_types():
    types_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    # Wipe original headers that conflict with our minimal definitions
    headers_to_wipe = [
        'include/2.0L/PR/libaudio.h',
        'include/2.0L/PR/n_libaudio.h',
        'include/2.0L/PR/os.h',
        'include/2.0L/PR/gu.h',
        'include/2.0L/PR/gbi.h',
        'include/n_synth.h',
        'include/synthInternals.h'
    ]

    for header in headers_to_wipe:
        if os.path.exists(header):
            with open(header, 'w') as f:
                f.write("// Silenced by fix_n64_types.py\n")

    content = """#ifndef _BKA_ANDROID_N64_TYPES_H_
#define _BKA_ANDROID_N64_TYPES_H_

/**
 * FOUNDATION TYPES
 */
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
#include <math.h>

// --- MATH CONSTANTS & MACROS ---
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define DEGREES_TO_RADIANS(d) ((d) * M_PI / 180.0)
#define RADIANS_TO_DEGREES(r) ((r) * 180.0 / M_PI)

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

// --- OS & KERNEL ---
typedef s32 OSPri;
typedef void* OSMesg;
typedef u32 OSIntMask;

#define OS_IM_NONE 0
#define OS_STATE_STOPPED    1
#define OS_STATE_RUNNABLE   2
#define OS_STATE_RUNNING    4
#define OS_STATE_WAITING    8

typedef struct {
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

// --- PI (PARALLEL INTERFACE) & DMA ---
typedef struct {
    OSMesg      hdr;
    u32         devAddr;
    void        *dramAddr;
    u32         size;
    OSMesgQueue *retQueue;
} OSIoMesg;

typedef struct {
    u8  type;
    u32 baseAddr;
    u32 latency;
    u32 pulse;
    u32 pageSize;
    u32 relDuration;
    u32 domain;
} OSPiHandle;

// --- CONTROLLER ---
typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;

// --- GRAPHICS (GBI) ---
typedef u64 Gfx;
typedef struct { s32 m[4][4]; } Mtx;
typedef struct {
    short ob[3];
    u16   flag;
    short tc[2];
    u8    cn[4];
} Vtx_t;
typedef union { Vtx_t v; long long force_alignment; } Vtx;

// --- AUDIO STRUCTURES ---
typedef s32 ALMicroTime;
typedef s32 ALPan;
typedef u64 Acmd;

typedef struct {
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

typedef struct {
    ALMicroTime attackTime;
    ALMicroTime decayTime;
    ALMicroTime releaseTime;
    u8          attackVolume;
    u8          decayVolume;
} ALEnv;

typedef struct {
    ALMicroTime attackTime;
    ALMicroTime decayTime;
    ALMicroTime releaseTime;
    u8          attackVolume;
    u8          decayVolume;
} ALEnvelope;

typedef struct {
    u8 velocityMin;
    u8 velocityMax;
    u8 keyMin;
    u8 keyMax;
    u8 keyBase;
    u8 detune;
} ALKeyMap;

typedef struct {
    u32 start;
    u32 end;
    u32 count;
    s16 state[16];
} ALADPCMloop;

typedef struct {
    s32 order;
    s32 npredictors;
    s16 book[1]; 
} ALADPCMBook;

typedef struct {
    ALADPCMloop *loop;
    ALADPCMBook *book;
} ALADPCMWaveInfo;

typedef struct {
    void *loop;
} ALRawWaveInfo;

typedef struct ALWaveTable_s {
    u8 *base;
    u32 len;
    u8  type;
    u8  flags;
    union {
        ALADPCMWaveInfo adpcmWave;
        ALRawWaveInfo   rawWave;
    } waveInfo;
} ALWaveTable;

typedef struct {
    ALEnvelope  *envelope;
    ALKeyMap    *keyMap;
    ALWaveTable *wavetable;
    u8  samplePan;
    u8  sampleVolume;
    u8  flags;
} ALSound;

typedef struct ALInstrument_s {
    u8          volume;
    u8          pan;
    u8          priority;
    u8          flags;
    u16         tremType;
    u16         tremRate;
    u16         tremDepth;
    u16         tremDelay;
    u16         vibType;
    u16         vibRate;
    u16         vibDepth;
    u16         vibDelay;
    s16         bendRange;
    u16         soundCount;
    ALSound     *soundArray[1];
} ALInstrument;

typedef struct {
    u8          *base;
    u16         instCount;
    u8          flags;
    ALInstrument *percussion;
    ALInstrument *instArray[1];
} ALBank;

typedef struct {
    u16         revision;
    u16         bankCount;
    ALBank      *bankArray[1];
} ALBankFile;

typedef struct {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

typedef struct {
    ALLink      freeList;
    ALLink      allocList;
} ALEvtq;

typedef struct {
    u32 unk0;
    u16 unkA;
} ALChanState;

typedef struct {
    ALEvtq       evtq;
    ALChanState  chanState[16];
    u8           reserved[1024];
} ALCSPlayer;

typedef ALCSPlayer N_ALCSPlayer;

// --- N_ALVoice (used by n_synstartvoice*.c) ---
typedef struct ALPVoice_s ALPVoice;

typedef struct N_ALVoice_s {
    struct N_ALVoice_s *next;
    ALPVoice           *pvoice;
    s16                 unityPitch;
} N_ALVoice;

typedef struct ALPVoice_s {
    s32 offset;
} ALPVoice;

// --- Param structures for voice start ---
typedef struct {
    s32          delta;
    s32          type;
    ALWaveTable *wave;
    void        *next;
    s16          unity;
} ALStartParam;

typedef struct {
    s32          delta;
    void        *next;
    s32          type;
    s16          unity;
    ALPan        pan;
    u8           volume;
    u8           fxMix;
    s16          pitch;
    s32          samples;
    ALWaveTable *wave;
} ALStartParamAlt;

// --- MIXER & FILTERS ---
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

typedef struct {
    ALFilter    filter;
    s32         sourceCount;
    s32         maxSources;
    ALFilter    **sources;
} ALAuxBus;

typedef struct {
    ALFilter    filter;
    s32         paramSamples;   // required by n_synstartvoice*.c
    u8          reserved[1020];
} ALSyn;

typedef struct {
    ALSyn *drvr;
    u8    reserved[1024];
} ALGlobals;

// --- AUDIO CONSTANTS ---
#define AL_ADPCM_WAVE             0
#define AL_RAW16_WAVE             1
#define AL_BANK_VERSION           1
#define AL_SEQP_MIDI_EVT          2
#define AL_MIDI_ControlChange     0xB0
#define AL_UNK18_EVT              18
#define ERR_ALBNKFNEW             10
#define AL_AUX_L_OUT              0
#define AL_AUX_R_OUT              1

// Filter / param constants used across core1/audio/
#define AL_FILTER_ADD_SOURCE      0x01   // <-- This was missing
#define AL_FILTER_START_VOICE     0x10
#define AL_FILTER_START_VOICE_ALT 0x11
#define AL_FILTER_ADD_UPDATE      0x20
#define ERR_ALSYN_NO_UPDATE       100

#ifdef __cplusplus
extern "C" {
#endif

extern ALGlobals *alGlobals;
extern ALSyn     *n_syn;
extern OSThread  *__osRunningThread;

void alEvtqPostEvent(ALEvtq *evtq, ALEvent *evt, ALMicroTime delta);
void alFilterNew(ALFilter *f, ALCmdHandler h, ALSetParam s, s32 type);

void *__n_allocParam(void);
void n_alEnvmixerParam(void *pvoice, s32 type, void *update);

#define ALFailIf(cond, err) if (cond) return;

#ifdef __cplusplus
}
#endif

#endif
"""

    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h updated with AL_FILTER_ADD_SOURCE and previous audio fixes.")

if __name__ == '__main__':
    fix_n64_types()