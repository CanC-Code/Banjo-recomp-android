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

    print("Step 1: Wiping conflicting SDK headers...")
    for header in headers_to_wipe:
        if os.path.exists(header):
            with open(header, 'w') as f:
                f.write("// Silenced by fix_n64_types.py\n")
            print(f"  ✅ {header}")

    print(f"\nStep 2: Injecting Geometry, Input, and Audio types into {types_path}...")
    content = """#ifndef _BKA_ANDROID_N64_TYPES_H_
#define _BKA_ANDROID_N64_TYPES_H_

#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif

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

// --- OS, KERNEL & INPUT ---
typedef s32  OSPri;
typedef void* OSMesg;
typedef struct { u32 valid; u32 msgCount; OSMesg *msg; } OSMesgQueue;

typedef struct {
    u16     button;
    s8      stick_x;
    s8      stick_y;
    u8      errno;
} OSContPad;

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

// --- GRAPHICS & GEOMETRY ---
typedef uint64_t Gfx;
typedef struct { int32_t m[4][4]; } Mtx;

// Vertex structure used for 3D models
typedef struct {
    short   ob[3];   /* x, y, z */
    u16     flag;
    short   tc[2];   /* texture coord s, t */
    u8      cn[4];   /* color/normal r, g, b, a */
} Vtx_t;

typedef union {
    Vtx_t          v;
    long long int  force_structure_alignment;
} Vtx;

typedef struct {
    u8      col[3];
    s8      pad1;
    u8      colc[3];
    s8      pad2;
    s8      dir[3];
    s8      pad3;
} Light_t;

typedef union {
    Light_t         l;
    long long int   force_structure_alignment;
} Light;

// --- AUDIO DATA STRUCTURES ---
typedef s32 ALMicroTime;
typedef s32 ALPan;

typedef struct {
    u8      *base;
    u8      *cur;
    s32     len;
    s32     count;
} ALHeap;

#define AL_ADPCM_WAVE   0
#define AL_RAW16_WAVE   1

typedef struct { u32 start; u32 end; u32 count; } ALRawLoop;
typedef struct { u32 start; u32 end; u32 count; s16 state[16]; } ALADPCMloop;
typedef struct { u32 order; u32 npredictors; s16 book[1]; } ALADPCMBook;
typedef struct { ALADPCMloop *loop; ALADPCMBook *book; } ALADPCMWaveInfo;

typedef union {
    ALADPCMWaveInfo adpcmWave;
    struct { ALRawLoop *loop; } rawWave;
} ALWaveInfo;

typedef struct {
    u8 *base;
    s32 len;
    u8 type;
    u8 flags;
    ALWaveInfo waveInfo;
} ALWaveTable;

typedef struct {
    ALMicroTime attackTime;
    ALMicroTime decayTime;
    ALMicroTime releaseTime;
    u8 attackVolume;
    u8 decayVolume;
} ALEnvelope;

typedef struct {
    u8 velocityMin; u8 velocityMax; u8 keyMin; u8 keyMax; u8 keyBase; s8 detune;
} ALKeyMap;

typedef struct {
    ALWaveTable *wavetable;
    ALEnvelope *envelope;
    ALKeyMap *keyMap;
    u8 samplePan;
    u8 sampleVolume;
    u8 flags;
} ALSound;

typedef struct {
    u8 volume; u8 pan; u8 priority; u8 soundCount; ALSound *sounds[1];
} ALInstrument;

typedef struct { s16 instCount; ALInstrument *instArray[1]; } ALBank;
typedef struct { s16 revision; s16 bankCount; ALBank *bankArray[1]; } ALBankFile;

typedef struct { u8 *offset; s32 len; } ALSeqData;
typedef struct { s16 seqCount; ALSeqData seqArray[1]; } ALSeqFile;

// --- AUDIO EVENTS & PLAYERS ---
typedef struct {
    s16 type;
    union {
        struct { f32 unk0; f32 unk4; } unk18;
        s32 word;
    } msg;
} ALEvent;

#define AL_UNK18_EVT    18

typedef struct {
    struct ALFilter_s *source;
    int32_t (*handler)(void *, int16_t *, int32_t, int32_t, void *);
} ALFilter;

typedef struct {
    ALFilter filter;
    u8 evtq[64]; 
} ALCSPlayer;

typedef ALCSPlayer N_ALCSPlayer;

typedef struct {
    u8 data[1024];
} ALSyn;

typedef struct {
    ALSyn *drvr;
    u8    reserved[1024];
} ALGlobals;

// --- GLOBALS & PROTOTYPES ---
#ifdef __cplusplus
extern "C" {
#endif
extern ALGlobals *alGlobals;
extern ALSyn *n_syn;
extern OSThread *__osRunningThread;

void alEvtqPostEvent(void *evtq, ALEvent *evt, ALMicroTime delta);
void n_alEnvmixerParam(void *v, s32 p, void *ptr);
s32 _n_timeToSamples(ALMicroTime t);
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
