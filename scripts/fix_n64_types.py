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

    print(f"\\nStep 2: Injecting Math Constants and Kernel Types into {types_path}...")
    content = """#ifndef _BKA_ANDROID_N64_TYPES_H_
#define _BKA_ANDROID_N64_TYPES_H_

#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES
#endif

#include <stdint.h>
#include <stddef.h>
#include <math.h>

// --- MATH CONSTANTS ---
// Explicitly define M_PI if the compiler's math.h is being shy
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Degrees to Radians conversion used in many N64 games
#ifndef M_DTOR
#define M_DTOR 0.017453292519943295
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

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif
#ifndef NULL
#define NULL 0
#endif

// --- OS / KERNEL / THREADING ---
typedef s32  OSPri;
typedef void* OSMesg;

typedef struct { u32 valid; u32 msgCount; OSMesg *msg; } OSMesgQueue;

typedef struct {
    OSMesg      hdr;
    u32         devAddr;
    void        *dramAddr;
    u32         size;
    OSMesgQueue *retQueue;
} OSIoMesg;

typedef struct {
    u32 type; u32 baseAddr; u8 latency; u8 pulse; u8 pageSize; u8 relDuration;
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

// --- INPUT / CONTROLLER ---
typedef struct {
    u16     button;
    s8      stick_x;
    s8      stick_y;
    u8      errno;
} OSContPad;

typedef struct {
    u16     type;
    u8      status;
    u8      errno;
} OSContStatus;

typedef struct { u8 data[128]; } OSTask;

// --- GRAPHICS (RCP) ---
typedef uint64_t Gfx;
typedef uint64_t Acmd;
typedef struct { int32_t m[4][4]; } Mtx;

typedef struct {
    short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4];
} Vtx_t;

typedef struct {
    short ob[3]; unsigned short flag; short tc[2]; signed char n[3]; unsigned char a;
} Vtx_n;

typedef union {
    Vtx_t v; Vtx_n n; long long int force_align;
} Vtx;

typedef struct { short vscale[4]; short vtrans[4]; } Vp;

// --- AUDIO ENGINE ---
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
typedef struct { u8 volume; u8 pan; u8 priority; u8 soundCount; ALSound *sounds[1]; } ALInstrument;
typedef struct { s16 instCount; ALInstrument *instArray[1]; } ALBank;
typedef struct { s16 revision; s16 bankCount; ALBank *bankArray[1]; } ALBankFile;
typedef struct { s16 seqCount; u8 *data; } ALSeqFile;

typedef struct { u8 data[1024]; } ALGlobals;
typedef struct { u8 *base; u8 *cur; s32 len; s32 count; } ALHeap;
typedef struct { s32 paramSamples; } ALSyn;

typedef struct { u32 offset; } ALVoice;
typedef struct { ALVoice *pvoice; f32 unityPitch; } N_ALVoice;

typedef struct { void *next; s32 delta; u32 type; ALWaveTable *wave; f32 unity; } ALStartParam;
typedef struct { void *next; s32 delta; u32 type; ALWaveTable *wave; f32 pitch; f32 unity; s16 volume; ALPan pan; u8 fxMix; s32 samples; } ALStartParamAlt;

// --- PROTOTYPES ---
#ifdef __cplusplus
extern "C" {
#endif
extern ALSyn *n_syn;
void n_alEnvmixerParam(ALVoice *v, s32 p, void *ptr);
void* __n_allocParam(void);
s32 _n_timeToSamples(ALMicroTime t);
OSThread *mainThread_get(void);
OSContPad *func_8024F3F4(void);
#ifdef __cplusplus
}
#endif

#define AL_FILTER_START_VOICE     1
#define AL_FILTER_START_VOICE_ALT 2
#define AL_FILTER_ADD_UPDATE      3
#define ALFailIf(cond, err)       if(cond) return

#endif // _BKA_ANDROID_N64_TYPES_H_
"""
    
    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print(f"✅ Updated: {types_path}")

if __name__ == '__main__':
    fix_n64_types()
