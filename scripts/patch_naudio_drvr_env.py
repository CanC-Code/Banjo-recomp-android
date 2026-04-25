import os
import re

def patch_naudio_drvr_env():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path):
        print(f"File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Expand ALParam_s to include delta, type, and moredata unions
    alparam_regex = r'typedef\s+struct\s+ALParam_s\s*\{[^}]*\}\s*ALParam;'
    expanded_alparam = """typedef struct ALParam_s {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    union {
        s32 i;
        f32 f;
    } moredata;
    union { f32 f; s32 i; } data;
    s32 paramID;
} ALParam;"""
    if "moredata" not in content:
        content = re.sub(alparam_regex, expanded_alparam, content)

    # 2. Fix ALSynConfig to allow integer switching on fxType and provide params array
    alsynconfig_regex = r'typedef\s+struct\s*\{[^}]*maxVVoices[^}]*\}\s*ALSynConfig;'
    expanded_alsynconfig = """typedef struct {
    u32 maxVVoices;
    u32 maxPVoices;
    u32 maxUpdates;
    u32 maxEvents;
    void *heap;
    u32 outputRate;
    s16 fxType;
    s16 *params;
} ALSynConfig;"""
    if "s16 *params;" not in content:
        content = re.sub(alsynconfig_regex, expanded_alsynconfig, content)

    # 3. Inject Missing Event and Filter Macros
    if "AL_SEQP_STOPPING_EVT" not in content:
        content = content.replace(
            "#define AL_SEQ_MIDI_EVT         19",
            "#define AL_SEQ_MIDI_EVT         19\n"
            "#define AL_SEQP_STOPPING_EVT    20\n\n"
            "#define AL_FILTER_SET_PAN       1\n"
            "#define AL_FILTER_SET_VOLUME    2\n"
            "#define AL_FILTER_SET_FXAMT     3\n"
            "#define AL_FX_CUSTOM            1\n"
        )

    # 4. Replace ALFx forward declaration with concrete structs and resolve aliases
    alfx_regex = r'typedef\s+struct\s+ALFx_s\s+ALFx;'
    full_alfx = """typedef struct {
    s32 input;
    s32 output;
    s16 ffcoef;
    s16 fbcoef;
    s16 gain;
    f32 delay;
} ALDelay;

typedef struct {
    u8 pad[32];
} ALLowPass;

typedef s32 (*ALSetFXParam)(void *, s32, void *);

typedef struct ALFx_s {
    ALFilter filter;
    s16 length;
    s16 *base;
    s16 *input;
    u8 section_count;
    ALDelay *delay;
    ALSetFXParam paramHdl;
} ALFx;

/* Link older libaudio typedefs to their specialized N_ variants */
typedef N_PVoice PVoice;
typedef N_ALSyn ALSynth;

typedef struct {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    PVoice *pvoice;
} ALFreeParam;"""
    
    if "ALDelay" not in content:
        content = re.sub(alfx_regex, full_alfx, content)

    with open(header_path, 'w') as f:
        f.write(content)
    print("✅ n64_types.h successfully patched with extended libaudio Driver/Env definitions.")

if __name__ == '__main__':
    patch_naudio_drvr_env()
