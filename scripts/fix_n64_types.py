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

#define OS_STATE_STOPPED    1
#define OS_STATE_RUNNABLE   2
#define OS_STATE_RUNNING    4
#define OS_STATE_WAITING    8

#define OS_PRIORITY_IDLE    0
#define OS_PRIORITY_RMON    250
#define OS_PRIORITY_VIMGR   254

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

// --- AUDIO TYPES & BANK SYSTEM ---
typedef s32 ALMicroTime;
typedef s32 ALPan;
typedef u64 Acmd;

// ADPCM / Wave Types
#define AL_ADPCM_WAVE   0
#define AL_RAW16_WAVE   1

typedef struct {
    u32 order;
    u32 npredictors;
    s16 *book;
} ALADPCMBook;

typedef struct {
    u32 start;
    u32 end;
    u32 count;
    s16 state[16];
} ALADPCMloop, ALRawLoop;

typedef struct {
    u8          *base;
    s32         len;
    u8          type;
    u8          flags;
    union {
        struct {
            ALADPCMloop *loop;
            ALADPCMBook *book;
        } adpcmWave;
        struct {
            ALRawLoop   *loop;
        } rawWave;
    } waveInfo;
} ALWaveTable;

typedef struct {
    ALWaveTable *wavetable;
    u8          samplePan;
    u8          sampleVolume;
    f32         reverb;
} ALSound;

typedef struct {
    u8          volume;
    u8          pan;
    u8          priority;
    u8          flags;
    u8          tremType;
    u8          tremRate;
    u8          tremDepth;
    u8          tremDelay;
    u8          vibType;
    u8          vibRate;
    u8          vibDepth;
    u8          vibDelay;
    s16         bendRange;
    s16         soundCount;
    ALSound     *soundArray[1];
} ALInstrument;

typedef struct {
    s16         instCount;
    u8          *flags;
    ALInstrument *instArray[1];
} ALBank;

typedef struct {
    u32         revision;
    s16         bankCount;
    ALBank      *bankArray[1];
} ALBankFile;

typedef struct {
    s32         instrumentCount;
    ALInstrument **instruments;
} ALSeqFile;

// --- SEQUencer / PLAYER ---
typedef struct {
    u8 reserved[256];
} ALCSPlayer;

// --- FILTER & SYNTH ---
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

#define AL_FILTER_START_VOICE     1
#define AL_FILTER_START_VOICE_ALT 2
#define AL_FILTER_ADD_UPDATE      3
#define AL_FILTER_ADD_SOURCE      4
#define ERR_ALSYN_NO_UPDATE       100

// Event System
#define AL_UNK18_EVT    18

typedef struct {
    s32 type;
    union {
        struct {
            f32 unk0;
            f32 unk4;
        } unk18;
        u8 raw[32];
    } msg;
} ALEvent;

typedef struct ALLink_s {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

typedef struct {
    ALLink      node;
    s32         delta;
    ALEvent     evt;
} ALEventListItem;

typedef struct {
    ALLink      freeList;
    ALLink      allocList;
} ALEvtq;

typedef ALEvtq ALEventQueue;

// --- SYNTH GLOBALS ---
typedef struct {
    PVoice      *pVoiceList;
    s32         paramSamples;
} ALSyn;

typedef struct {
    ALSyn *drvr;
} ALGlobals;

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
    print(f"✅ Audio Bank & Sequence Player Support Added: {types_path}")

if __name__ == '__main__':
    fix_n64_types()
