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

    print(f"\nStep 2: Injecting Heavy-Duty N64 types into {types_path}...")
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

// --- OS THREAD STATE FLAGS ---
#define OS_STATE_STOPPED    1
#define OS_STATE_RUNNABLE   2
#define OS_STATE_RUNNING    4
#define OS_STATE_WAITING    8

// --- OS & KERNEL TYPES ---
typedef s32 OSPri;
typedef void* OSMesg;

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

typedef struct OSIoMesg_s {
    OSMesg      hdr;
    u32         devAddr;
    void        *dramAddr;
    u32         size;
    OSMesgQueue *retQueue;
} OSIoMesg;

typedef struct OSPiHandle_s {
    u8  type;
    u32 baseAddr;
    u32 latency;
    u32 pulse;
    u32 pageSize;
    u32 relDuration;
    u32 domain;
} OSPiHandle;

// --- CONTROLLER INPUT TYPES ---
typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;

typedef struct {
    u8  type;
    u8  status;
    u8  errno;
} OSContStatus;

// --- GRAPHICS (GBI) ---
typedef uint64_t Gfx;

typedef struct {
    short ob[3];
    u16 flag;
    short tc[2];
    u8 cn[4];
} Vtx_t;

typedef union {
    Vtx_t v;
    long long force_alignment;
} Vtx;

// --- AUDIO TYPES ---
typedef s32 ALMicroTime;
typedef s32 ALPan;
typedef uint64_t Acmd;

typedef struct {
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

// AL filter event codes
#define AL_FILTER_ADD_UPDATE       8
#define AL_FILTER_START_VOICE      7
#define AL_FILTER_START_VOICE_ALT  9
#define AL_FILTER_ADD_SOURCE       6
#define ERR_ALSYN_NO_UPDATE        3000

// AL aux bus buffer IDs
#define AL_AUX_L_OUT               4
#define AL_AUX_R_OUT               5

// AL wave type codes
#define AL_ADPCM_WAVE              0
#define AL_RAW16_WAVE              1

// AL event type codes
#define AL_UNK18_EVT               0x18
#define AL_SEQP_MIDI_EVT           0x06
#define AL_SEQP_PLAY_EVT           0x01
#define AL_SEQP_BANK_EVT           0x04
#define AL_TEMPO_EVT               0x03
#define AL_TRACK_END               0xFF

// AL MIDI status bytes
#define AL_MIDI_ControlChange      0xB0
#define AL_MIDI_ChannelModeSelect  0xB0
#define AL_MIDI_Meta               0xFF

// AL MIDI meta event types
#define AL_MIDI_META_TEMPO         0x51

// AL bank version and error codes
#define AL_BANK_VERSION            0x4231
#define ERR_ALBNKFNEW              0x0500

typedef struct ALFilter_s {
    struct ALFilter_s *source;
    int32_t (*handler)(void *, int16_t *, int32_t, int32_t, void *);
} ALFilter;

#define AL_MAX_SOURCES  8

typedef struct {
    ALFilter        filter;
    ALFilter        **sources;
    s32             sourceCount;
} ALAuxBus;

typedef struct PVoice_s {
    ALFilter    filter;
    struct PVoice_s *next;
    s32         offset;
} PVoice;

typedef struct N_ALVoice_s {
    PVoice      *pvoice;
    ALPan       pan;
    u8          volume;
    u8          fxMix;
    f32         pitch;
    f32         unityPitch;
} N_ALVoice;

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

// --- AUDIO WAVE / SAMPLE TYPES ---
typedef struct {
    s32         order;
    s32         npredictors;
    s16         book[1];
} ALADPCMBook;

typedef struct {
    u32         start;
    u32         end;
    u32         count;
    s16         state[16];
} ALADPCMloop;

typedef struct {
    u32         start;
    u32         end;
    u32         count;
} ALRawLoop;

typedef struct {
    ALADPCMloop *loop;
    ALADPCMBook *book;
} ALADPCMWaveInfo;

typedef struct {
    ALRawLoop   *loop;
} ALRAWWaveInfo;

typedef struct {
    u8          *base;
    u32         baseLength;
    s32         type;
    u8          flags;
    union {
        ALADPCMWaveInfo adpcmWave;
        ALRAWWaveInfo   rawWave;
    } waveInfo;
} ALWaveTable;

// --- AUDIO BANK TYPES ---
typedef struct {
    s32         attackTime;
    s32         decayTime;
    s32         releaseTime;
    u8          attackVolume;
    u8          decayVolume;
} ALEnvelope;

typedef struct {
    u8          velocityMin;
    u8          velocityMax;
    u8          keyMin;
    u8          keyMax;
    u8          keyBase;
    u8          detune;
} ALKeyMap;

typedef struct {
    ALEnvelope  *envelope;
    ALKeyMap    *keyMap;
    ALWaveTable *wavetable;
    ALPan       pan;
    u8          volume;
    u8          flags;
    u8          pad[2];
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
    ALSound     **soundArray;
} ALInstrument;

typedef struct {
    s16         instCount;
    u8          flags;
    u8          pad;
    s32         sampleRate;
    ALInstrument *percussion;
    ALInstrument **instArray;
} ALBank;

typedef struct {
    s32         revision;
    s32         bankCount;
    ALBank      **bankArray;
} ALBankFile;

// --- SEQUENCE FILE ---
typedef struct {
    u8  *offset;
} ALSeqData;

typedef struct {
    s32         seqCount;
    ALSeqData   seqArray[1];
} ALSeqFile;

// --- COMPACT MIDI SEQUENCE TYPES ---
// ALCMidiHdr: header for a compact MIDI sequence blob
typedef struct {
    u16         division;   // ticks per quarter note (qnpt)
    u16         trackCount;
    u32         trackOffset[1];
} ALCMidiHdr;

// ALCSeq: compact sequence parser state
typedef struct {
    ALCMidiHdr  *base;
    u32         trackEnd[16];
    u32         trackPos[16];
    u8          lastStatus[16];
    s32         qnpt;       // quarter notes per tick (from header division)
    u32         trackCount;
} ALCSeq;

// --- AUDIO EVENT QUEUE TYPES ---
typedef struct {
    OSMesgQueue *msgQ;
    u32          head;
    u32          tail;
    u32          count;
} ALEvtq;

// ALEvent message sub-structs
typedef struct {
    s32  ticks;
    u8   status;
    u8   byte1;
    u8   byte2;
    u8   pad;
} ALMidiMsg;

typedef struct {
    u8   status;
    u8   type;
    u8   byte1;
    u8   byte2;
} ALTempoMsg;

typedef struct {
    ALBank  *bank;
} ALSPBankMsg;

typedef struct {
    f32 unk0;
    f32 unk4;
} ALUnk18Msg;

typedef struct {
    s32  type;
    union {
        ALMidiMsg   midi;
        ALTempoMsg  tempo;
        ALSPBankMsg spbank;
        ALUnk18Msg  unk18;
        u8          raw[16];
    } msg;
} ALEvent;

// --- CS PLAYER (compact sequence player) ---
#define AL_MAX_CHANNELS 16

typedef struct {
    u8  unkA;
    u8  pad[3];
} ALChanState;

typedef struct {
    ALEvtq      evtq;
    ALCSeq      *target;
    s32         uspt;       // microseconds per tick
    ALChanState chanState[AL_MAX_CHANNELS];
    u8          reserved[128];
} ALCSPlayer;

// N_ prefixed aliases used by decompiled source
typedef ALCSPlayer N_ALCSPlayer;

// N_ALSeqPlayer: sequence player (MIDI sequencer variant)
typedef struct {
    ALEvtq      evtq;
    u8          reserved[512];
} N_ALSeqPlayer;

// --- AUDIO PARAM UPDATE STRUCTS ---
typedef struct {
    s32             delta;
    void            *next;
    s32             type;
    ALWaveTable     *wave;
    f32             unity;
} ALStartParam;

typedef struct {
    s32             delta;
    void            *next;
    s32             type;
    f32             unity;
    ALPan           pan;
    u8              volume;
    u8              fxMix;
    f32             pitch;
    s32             samples;
    ALWaveTable     *wave;
} ALStartParamAlt;

// --- EXTERNALS ---
#ifdef __cplusplus
extern "C" {
#endif
extern ALGlobals *alGlobals;
extern ALSyn *n_syn;
extern OSThread *__osRunningThread;

void* __n_allocParam();
void n_alEnvmixerParam(void *filter, s32 paramID, void *ptr);
s32 _n_timeToSamples(ALMicroTime t);
void alEvtqPostEvent(ALEvtq *evtq, ALEvent *evt, ALMicroTime delta);
#define ALFailIf(cond, code) if(cond) return;
#ifdef __cplusplus
}
#endif

#endif // _BKA_ANDROID_N64_TYPES_H_
"""

    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ Full-Spectrum Header Created: {types_path}")

if __name__ == '__main__':
    fix_n64_types()