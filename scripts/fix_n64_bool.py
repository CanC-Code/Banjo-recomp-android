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

// --- MATH CONSTANTS ---
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

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

// Thread States
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

typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;

// --- GRAPHICS (GBI) ---
typedef u64 Gfx;

typedef struct {
    s32 m[4][4];
} Mtx;

typedef struct {
    short ob[3];
    u16   flag;
    short tc[2];
    u8    cn[4];
} Vtx_t;

typedef union {
    Vtx_t v;
    long long force_alignment;
} Vtx;

// --- AUDIO TYPES & N_AUDIO ---
typedef s32 ALMicroTime;
typedef s32 ALPan;
typedef u64 Acmd;

typedef struct {
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

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

typedef struct ALParam_s {
    struct ALParam_s    *next;
    s32                 delta;
    s32                 type;
} ALParam;

typedef struct {
    u8 *base;
    u32 len;
    u8  type;
    u8  flags;
    void *loop;
} ALWaveTable;

typedef struct PVoice_s {
    ALFilter    filter;
    struct PVoice_s *next;
    s32         offset;
} PVoice;

typedef struct {
    ALFilter    filter;
    PVoice      *pvoice;
    u16         unityPitch;
} N_ALVoice;

typedef struct ALStartParam_s {
    struct ALStartParam_s *next;
    s32 delta;
    s32 type;
    ALWaveTable *wave;
    u16 unity;
} ALStartParam;

typedef struct {
    struct ALParam_s *next;
    s32 delta;
    s32 type;
    u16 unity;
    ALPan pan;
    u16 volume;
    u16 fxMix;
    u16 pitch;
    s32 samples;
    ALWaveTable *wave;
} ALStartParamAlt;

// Audio Constants
#define AL_FILTER_START_VOICE     1
#define AL_FILTER_START_VOICE_ALT 2
#define AL_FILTER_ADD_UPDATE     3
#define ERR_ALSYN_NO_UPDATE      100

typedef struct {
    ALFilter            filter;
    ALParam             *ctrlList;
    ALParam             *freeList;
    s16                 *outBuf;
    s32                 lptr;
} ALEnvMixer;

typedef struct ALLink_s {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

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

typedef struct {
    PVoice      *pVoiceList;
    s32         paramSamples;
    u32         curSamples;
    u32         maxSamples;
} ALSyn;

typedef struct {
    ALSyn *drvr;
    u8    reserved[1024];
} ALGlobals;

typedef struct {
    s32  type;
    union {
        u8 raw[16];
    } msg;
} ALEvent;

// --- C++ COMPATIBILITY & EXTERNS ---
#ifdef __cplusplus
extern "C" {
#endif

extern ALGlobals *alGlobals;
extern ALSyn     *n_syn;
extern OSThread  *__osRunningThread;

void alFilterNew(ALFilter *f, ALCmdHandler h, ALSetParam s, s32 type);
void alLink(ALLink *ln, ALLink *to);
void alUnlink(ALLink *ln);
void alCopy(void *src, void *dst, s32 size);
OSIntMask osSetIntMask(OSIntMask mask);
void* alHeapAlloc(ALHeap *hp, s32 count, s32 size);
void* __n_allocParam();
s32 _n_timeToSamples(ALMicroTime t);
void n_alEnvmixerParam(PVoice *v, s32 type, void *ptr);

#define ALFailIf(cond, err) if (cond) return;

#ifdef __cplusplus
}
#endif

#endif // _BKA_ANDROID_N64_TYPES_H_
"""

    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ OS Thread States Added: {types_path}")

if __name__ == '__main__':
    fix_n64_types()
