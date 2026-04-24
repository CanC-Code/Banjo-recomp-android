import os

def fix_n64_types():
    """
    Generates a consolidated n64_types.h file to replace conflicting headers
    and resolve missing AL_SEQP events, audio engine types, struct members, and constants.
    """
    types_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    # Wipe original conflicting headers to prevent redefinition errors
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

// --- PI & DMA ---
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

typedef s32 (*ALDMAproc)(s32, s32, void *);
typedef ALDMAproc (*ALDMANew)(void **);

// --- CONTROLLER ---
typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;

// --- GRAPHICS ---
typedef u64 Gfx;
typedef struct { s32 m[4][4]; } Mtx;
typedef struct {
    short ob[3];
    u16   flag;
    short tc[2];
    u8    cn[4];
} Vtx_t;
typedef union { Vtx_t v; long long force_alignment; } Vtx;

// --- LINKED LIST & EVENT QUEUE ---
typedef struct ALLink_s {
    struct ALLink_s *next;
    struct ALLink_s *prev;
} ALLink;

typedef struct ALEvtq_s {
    ALLink      freeList;
    ALLink      allocList;
    s32         eventCount;
} ALEvtq;

// Define ALEventQueue mapping
typedef ALEvtq ALEventQueue;

// --- CHANNEL STATE ---
typedef struct {
    u32 unk0;
    u16 unkA;
} ALChanState;

// --- AUDIO STRUCTURES ---
typedef s32 ALMicroTime;
typedef u8 ALPan; 

typedef u64 Acmd;

typedef struct {
    s32 unk0;
    s32 unk4;
} ADPCM_STATE;

typedef struct {
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

// ALParam and aliases
typedef struct ALParam_s {
    struct ALParam_s *next;
    s32 delta;
    s32 type;
    union { f32 f; s32 i; } data;
    union { f32 f; s32 i; } moredata;
    union { f32 f; s32 i; } stillmoredata;
} ALParam;

typedef struct ALPVoice_s ALPVoice;
typedef ALPVoice PVoice;

typedef struct {
    struct ALParam_s *next;
    s32 delta;
    s32 type;
    PVoice *pvoice;
} ALFreeParam;

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
    u32 start;
    u32 end;
    u32 count;
} ALRawLoop;

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

// --- SEQUENCE FILE ---
typedef struct {
    u32 offset;
} ALSeqData;

typedef struct {
    u16      revision;
    u16      seqCount;
    ALSeqData seqArray[1];
} ALSeqFile;

// --- MIDI / CSEQ ---
typedef struct {
    u8 *base;
    u16 division;
    u32 trackOffset[16];
} ALCMidiHdr;

typedef struct ALCSeq_s {
    ALCMidiHdr *base;
    u8         *cur;
    u32         track;
    u32         delta;
    u8          runningStatus;
    u8          status;
    u32         validTracks;
    u32         lastDeltaTicks;
    u32         lastTicks;
    u8          deltaFlag;
    u8          lastStatus[16];
    u8          *curBUPtr[16];
    u32         curBULen[16];
    u8          *curLoc[16];
    u32         evtDeltaTicks[16];
    f32         qnpt;
} ALCSeq;

typedef ALCSeq ALSeq;

// --- ALCSeqMarker ---
typedef struct ALCSeqMarker_s {
    u32         ticks;
    u8          track;
    u32         validTracks;
    u32         lastTicks;
    u32         lastDeltaTicks;
    u8          *curLoc[16];
    u8          *curBUPtr[16];
    u32         curBULen[16];
    u8          lastStatus[16];
    u32         evtDeltaTicks[16];
} ALCSeqMarker;

// --- EVENTS ---
#define AL_SEQP_PLAY_EVT          0x01
#define AL_SEQP_MIDI_EVT          0x02
#define AL_SEQP_STOP_EVT          0x03
#define AL_SEQP_BANK_EVT          0x04  
#define AL_SEQP_SEQ_EVT           0x05  
#define AL_SEQP_VOL_EVT           0x06  
#define AL_SEQP_META_EVT          0x07  
#define AL_SEQP_STOPPING_EVT      0x08  

#define AL_SEQ_MIDI_EVT           0x02
#define AL_SEQ_END_EVT            0x04
#define AL_CSP_LOOPSTART          0x05
#define AL_CSP_LOOPEND            0x06
#define AL_TEMPO_EVT              0x51

#define AL_MIDI_NoteOn            0x90
#define AL_MIDI_NoteOff           0x80
#define AL_MIDI_KeyPressure       0xA0
#define AL_MIDI_ControlChange     0xB0
#define AL_MIDI_ProgramChange     0xC0
#define AL_MIDI_ChannelPressure   0xD0
#define AL_MIDI_PitchBend         0xE0
#define AL_MIDI_ChannelModeSelect 0xB0

#define AL_MIDI_Meta              0xFF
#define AL_MIDI_META_TEMPO        0x51
#define AL_MIDI_META_EOT          0x2F
#define AL_CMIDI_LOOPSTART_CODE   0x70
#define AL_CMIDI_LOOPEND_CODE     0x71
#define AL_CMIDI_BLOCK_CODE       0x72

#define AL_ADPCM_WAVE             0
#define AL_RAW16_WAVE             1

typedef struct {
    u32 ticks;
    u8  status;
    u8  byte1;
    u8  byte2;
    u32 duration;
} ALMIDIEvent;

typedef struct {
    f32 unk0;
    f32 unk4;
} ALUnk18Event;

// Sequence Player Event Structs
typedef struct {
    ALBank *bank;
} ALSpBankEvent;

typedef struct {
    ALCSeq *seq;
} ALSpSeqEvent;

typedef struct {
    s16 vol;
} ALSpVolEvent;

typedef struct {
    s32 type;
    union {
        ALMIDIEvent   midi;
        ALUnk18Event  unk18;
        ALSpBankEvent spbank;  
        ALSpSeqEvent  spseq;   
        ALSpVolEvent  spvol;   
        struct {
            u8 status;
            u8 type;
            u8 byte1;
            u8 byte2;
            u8 byte3;
        } tempo;
        u8 raw[32];
    } msg;
} ALEvent;

typedef struct ALEventListItem_s {
    ALLink      node;
    ALMicroTime delta;
    ALEvent     evt;
} ALEventListItem;

// --- ALCSPlayer / N_ALCSPlayer / N_ALSeqPlayer ---
typedef struct ALCSPlayer_s {
    ALEvtq       evtq;
    ALChanState  chanState[16];
    ALCSeq       *target;
    f32          uspt;
    u8           reserved[1024 - sizeof(ALCSeq*) - sizeof(f32)];
} ALCSPlayer;

typedef ALCSPlayer N_ALCSPlayer;
typedef ALCSPlayer N_ALSeqPlayer;

// --- N_ALVoice / voice param structs ---
typedef struct N_ALVoice_s {
    struct N_ALVoice_s *next;
    ALPVoice           *pvoice;
    s16                 unityPitch;
} N_ALVoice;

typedef struct ALPVoice_s {
    s32 offset;
} ALPVoice;

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
typedef Acmd *(*ALCmdHandler)(void *, s16 *, s32, s32, Acmd *);
typedef s32 (*ALSetParam)(void *, s32, void *);
typedef s32 (*ALSetFXParam)(void *, s32, void *);

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
    ADPCM_STATE *state;
    ADPCM_STATE *lstate;
    void        *dma;
    void        *dmaState;
    s32         lastsam;
    s32         first;
    s32         memin;
} ALLoadFilter;

// Filter Sub-States
typedef struct {
    s16 fccoef[16];
    s16 fcoff[16];
} POLEF_STATE;

typedef struct {
    s16 unk[16];
} RESAMPLE_STATE;

typedef struct {
    s32 unk[16];
} ENVMIX_STATE;

typedef struct {
    ALFilter filter;
    RESAMPLE_STATE *state;
    f32 delta;
    s32 first;
    s32 motion;
    f32 ratio;
    s32 upitch;
    void *ctrlList;
    void *ctrlTail;
} ALResampler;

typedef struct {
    ALFilter    filter;
    POLEF_STATE *fstate;
    s32         fc;
    s32         fgain;
    s32         first;
    struct {
        s16 fccoef[16];
    } fcvec;
} ALLowPass;

// Audio engine mix nodes & delays
typedef struct {
    s32 input;
    s32 output;
    s16 ffcoef;
    s16 fbcoef;
    s16 gain;
    f32 rsinc;
    f32 rsval;
    s32 rsfrac;
    s32 rsdelta;
    f32 rsgain;
    ALResampler *rs;
    ALLowPass *lp;
} ALDelay;

typedef struct {
    ALFilter filter;
    s16 *base;
    s16 *input;
    u32 length;
    ALDelay *delay;
    u8 section_count;
    ALSetFXParam paramHdl;
} ALFx;

typedef struct {
    ALFilter filter;
    s32      state;
    void     *dmaState;
    void     *dma;
} ALSave;

typedef struct {
    s32 maxVVoices;
    s32 maxPVoices;
    s32 maxUpdates;
    s32 maxFXbusses;
    s16 *params; 
    s32 fxType;
    s32 outputRate;
} ALSynConfig;

typedef struct ALEnvMixer_s {
    ALFilter filter;
    s32      state;
    s16      *first;
    ALMicroTime firstEndTime;
    s16      *next;
    ALMicroTime nextEndTime;
    s32      pitch;
    s32      step;
    s32      upitch;
    ALMicroTime envEndTime;
    f32      envLevel;
    f32      envStep;
    ALParam  *ctrlList;
    ALParam  *paramFreeList;
    
    // Mix Parameters
    s32      delta;
    s32      segEnd;
    s32      volume;
    s32      pan;
    s32      dryamt;
    s32      wetamt;
    s32      cvolL;
    s32      cvolR;
    
    // Added Envelope parameters
    s32      motion;
    s32      ltgt;
    s32      rtgt;
    s32      lratm;
    s32      lratl;
    s32      rratm;
    s32      rratl;
    ALParam  *ctrlTail;
    ALFilter **sources;
} ALEnvMixer;

typedef struct {
    ALFilter    filter;
    s32         sourceCount;
    s32         maxSources;
    ALFilter    **sources;
} ALAuxBus;

typedef ALAuxBus ALMainBus;

typedef struct {
    ALFilter    filter;
    s32         paramSamples;
    u8          reserved[1020];
} ALSyn;

typedef ALSyn ALSynth;

typedef struct {
    ALSyn *drvr;
    u8    reserved[1024];
} ALGlobals;


// --- AUDIO CONSTANTS ---
#define AL_BANK_VERSION           1
#define AL_UNK18_EVT              18
#define ERR_ALBNKFNEW             10
#define AL_AUX_L_OUT              0
#define AL_AUX_R_OUT              1
#define AL_MAIN_L_OUT             0
#define AL_MAIN_R_OUT             1

#define AL_RESAMPLER_OUT           0
#define AL_FILTER_SET_WAVETABLE    1
#define AL_FILTER_SET_PITCH        2
#define AL_FILTER_SET_UNITY_PITCH  3
#define AL_FILTER_START            4
#define AL_FILTER_SET_FXAMT        5
#define AL_FILTER_SET_PAN          6
#define AL_FILTER_SET_VOLUME       7

#define AL_FILTER_RESET            8
#define AL_FILTER_SET_SOURCE       9
#define AL_FILTER_STOP_VOICE       10
#define AL_FILTER_FREE_VOICE       11

#define AL_FX                 0
#define AL_FX_SMALLROOM       1
#define AL_FX_BIGROOM         2
#define AL_FX_ECHO            3
#define AL_FX_CHORUS          4
#define AL_FX_FLANGE          5
#define AL_FX_CUSTOM          6

#define AL_FILTER_ADD_SOURCE      0x01
#define AL_FILTER_START_VOICE     0x10
#define AL_FILTER_START_VOICE_ALT 0x11
#define AL_FILTER_ADD_UPDATE      0x20
#define ERR_ALSYN_NO_UPDATE       100

#define AL_TRACK_END              0xFF

#define AL_CACHE_ALIGN            15
#define AL_EVTQ_END               0x7FFFFFFF

#define AL_STOPPED                0
#define AL_PLAYING                1
#define AL_ADPCM                  10
#define AL_ENVMIX                 11
#define AL_RESAMPLE               12
#define AL_AUXBUS                 13
#define AL_MAINBUS                14
#define AL_SAVE                   15

#ifdef __cplusplus
extern "C" {
#endif

extern ALGlobals *alGlobals;
extern ALSyn     *n_syn;
extern OSThread  *__osRunningThread;

extern Acmd *alFxPull(void *, s16 *, s32, s32, Acmd *);
extern s32 alFxParamHdl(void *, s32, void *);
extern s32 alFxParam(void *, s32, void *);

extern Acmd *alEnvmixerPull(void *, s16 *, s32, s32, Acmd *);
extern s32 alEnvmixerParam(void *, s32, void *);

extern Acmd *alAdpcmPull(void *, s16 *, s32, s32, Acmd *);
extern s32 alLoadParam(void *, s32, void *);

extern Acmd *alResamplePull(void *, s16 *, s32, s32, Acmd *);
extern s32 alResampleParam(void *, s32, void *);

extern Acmd *alAuxBusPull(void *, s16 *, s32, s32, Acmd *);
extern s32 alAuxBusParam(void *, s32, void *);

extern Acmd *alMainBusPull(void *, s16 *, s32, s32, Acmd *);
extern s32 alMainBusParam(void *, s32, void *);

extern Acmd *alSavePull(void *, s16 *, s32, s32, Acmd *);
extern s32 alSaveParam(void *, s32, void *);

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

    # Ensure the directory exists before writing
    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    
    with open(types_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h updated: Added ALSave structures and ensured ALLoadFilter has both states.")

if __name__ == '__main__':
    fix_n64_types()
