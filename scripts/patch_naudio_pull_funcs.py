import os
import re

def sanitize_and_patch_types():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path):
        print(f"File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Expanded list includes all AL, OS, PI, Graphics, and Controller dependencies
    types_to_clean = [
        'ALPan', 'Acmd', 'ADPCM_STATE', 'ALRawLoop', 
        'RESAMPLE_STATE', 'POLEF_STATE', 'ALSynConfig', 
        'Vtx_t', 'Vtx_n', 'Vtx', 'ALDMANew', 'ALDMAproc',
        'ALMicroTime', 'ALFilter', 'ALParam', 'N_ALFilter',
        'N_ALSyn', 'ALEvtq', 'ALEvent', 'ALVoiceHandler', 'ALSetParam',
        'ALCmdHandler', 'N_PVoice', 'ALVoice', 'ALVoiceConfig', 'N_ALVoice',
        'ALWaveTable', 'ALStartParam', 'ALStartParamAlt', 'ALAuxBus', 'ALFx',
        'OSMesg', 'OSMesgQueue', 'OSPiHandle', 'OSIoMesg', 'OSThread', 
        'f32', 'f64', 'Gfx', 'Mtx_t', 'Mtx', 'Sprite', 'OSContPad', 'ALHeap'
    ]

    # 2. Aggressively strip existing definitions (handles multi-line structs/unions)
    for t in types_to_clean:
        # Matches: typedef struct/union [Optional_Tag] { ... } TypeName;
        content = re.sub(rf'typedef\s+(struct|union)\s+([a-zA-Z0-9_]+\s*)?{{.*?}}\s*{t}\s*;', '', content, flags=re.DOTALL)
        # Matches single-line primitive typedefs
        content = re.sub(rf'typedef\s+[^;{{}}]+?\s*{t}\s*;', '', content)

    # 3. Inject the comprehensive libultra BK-types block
    bk_types_block = """
#ifndef _BK_SDK_TYPES_H_
#define _BK_SDK_TYPES_H_

/* Basic Primitives */
typedef float f32;
typedef double f64;

/* Hardware and Input Types */
typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errcode;
} OSContPad;

/* N64 Standard Audio primitives */
typedef s32 ALMicroTime;
typedef s32 ALPan;

/* Audio Function Pointers */
typedef void (*ALVoiceHandler)(void *);
typedef s32  (*ALSetParam)(void *, s32, void *);
typedef void (*ALCmdHandler)(void *, s16, void *);

typedef struct ALWaveTable_s ALWaveTable;
typedef struct ALFx_s ALFx;

/* Standard N64 Libaudio Structs */
typedef struct ALFilter_s {
    struct ALFilter_s   *source;
    ALVoiceHandler      handler;
    ALSetParam          setParam;
    short               inp;
    short               outp;
    int                 type;
} ALFilter;

typedef struct ALAuxBus_s {
    ALFilter    filter;
    s32         sourceCount;
    s32         maxSources;
    ALFilter    **sources;
    ALFx        *fx;
} ALAuxBus;

typedef struct N_ALFilter_s {
    struct N_ALFilter_s *source;
    ALVoiceHandler      handler;
    ALSetParam          setParam;
    short               inp;
    short               outp;
    int                 type;
} N_ALFilter;

typedef struct ALParam_s {
    struct ALParam_s    *next;
    s32                 paramID;
    union { f32 f; s32 i; } data;
} ALParam;

typedef struct {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    s16 unity;
    ALWaveTable *wave;
} ALStartParam;

typedef struct {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    s16 unity;
    u8 pan;
    u8 volume;
    u8 fxMix;
    u8 _pad;
    f32 pitch;
    s32 samples;
    ALWaveTable *wave;
} ALStartParamAlt;

typedef struct ALEvent_s {
    s16 type;
    union { s32 i[3]; void *p[3]; } msg;
} ALEvent;

typedef struct {
    u8 *base;
    u8 *cur;
    s32 len;
    s32 count;
} ALHeap;

/* Opaque/padded blobs to satisfy compiler size checks */
typedef struct ALEvtq_s {
    u8 pad[128];
} ALEvtq;

typedef struct ALVoice_s {
    u8 pad[64];
} ALVoice;

typedef struct ALVoiceConfig_s {
    s16 priority;
    s16 fxBus;
    u8 unityPitch;
} ALVoiceConfig;

/* Specific N_Audio definitions replacing earlier opaque blobs */
typedef struct N_PVoice_s {
    void *node_next;
    void *node_prev;
    struct N_ALVoice_s *vvoice;
    ALFilter *channelKnob;
    void *decoder;
    void *resampler;
    void *envmixer;
    s32 offset;
    u8 pad[64];
} N_PVoice;

typedef struct N_ALVoice_s {
    void *node_next;
    void *node_prev;
    N_PVoice *pvoice;
    ALWaveTable *table;
    void *clientPrivate;
    s16 state;
    s16 priority;
    s16 fxBus;
    s16 unityPitch;
} N_ALVoice;

typedef struct N_ALSyn_s {
    void *node_next;
    void *node_prev;
    s32 outputRate;
    s32 maxOutSamples;
    void *drvr;
    void *head;
    void *mainBus;
    void *auxBus;
    void *filterList;
    s32 paramSamples;
    u8 pad[512];
} N_ALSyn;

/* Graphics and Sequence Types */
typedef struct { u32 words[2]; } Acmd;
typedef struct { u32 w0; u32 w1; } Gfx;
typedef long Mtx_t[4][4];
typedef union { Mtx_t m; long long int force_structure_alignment; } Mtx;
typedef struct sprite Sprite;

typedef struct { s16 ob[16]; } ADPCM_STATE;
typedef struct { u32 start; u32 end; u32 count; ADPCM_STATE *state; } ALRawLoop;
typedef struct { u32 force_alignment; } RESAMPLE_STATE, POLEF_STATE;

typedef struct {
    u32 maxVVoices; u32 maxPVoices; u32 maxUpdates; u32 maxEvents;
    void *heap; u32 outputRate; void *fxType;
} ALSynConfig;

typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef struct { short ob[3]; unsigned short flag; short tc[2]; signed char n[3]; unsigned char a; } Vtx_n;
typedef union { Vtx_t v; Vtx_n n; long long int force_alignment; } Vtx;

typedef s32 (*ALDMAproc)(s32, s32, void *);
typedef ALDMAproc (*ALDMANew)(void *state);

/* OS Thread and PI / IO Message Types */
#ifndef _OS_THREAD_GUARD
#define _OS_THREAD_GUARD
typedef struct OSThread_s {
    struct OSThread_s   *next;
    s32                 priority;
    struct OSThread_s   **queue;
    struct OSThread_s   *tlnext;
    u16                 state;
    u16                 flags;
    s32                 id;
    int                 fp;
    u64                 context_pad[38]; /* Standard OSThreadContext size wrapper */
} OSThread;
#endif

typedef void * OSMesg;

typedef struct OSMesgQueue_s {
    OSThread *mtqueue;
    OSThread *fullqueue;
    s32 validCount;
    s32 first;
    s32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct OSPiHandle_s {
    struct OSPiHandle_s *next;
    u8 type;
    u8 latency;
    u8 pageSize;
    u8 relDuration;
    u8 pulse;
    u8 domain;
    u32 baseAddress;
    u32 speed;
    u32 transferInfo;
} OSPiHandle;

typedef struct OSIoMesg_s {
    u16 hdr;
    u8 err;
    u8 flags;
    OSPiHandle *piHandle;
    u32 devAddr;
    void *dramAddr;
    u32 size;
    OSMesgQueue *mq;
    OSMesg msg;
} OSIoMesg;

#endif
"""
    # 4. Insert immediately after the base s64/u64 primitives
    match = re.search(r'typedef.*s64;', content)
    if match:
        content = content[:match.end()] + bk_types_block + content[match.end():]
    else:
        content = bk_types_block + content

    with open(header_path, 'w') as f:
        f.write(content)
    print("✅ n64_types.h sanitized and extended BK graphics/audio/OS types re-injected.")

if __name__ == '__main__':
    sanitize_and_patch_types()
