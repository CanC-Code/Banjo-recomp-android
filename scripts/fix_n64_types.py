import os
import re

def patch_audio_engine():
    """
    Comprehensive patch for the N_Audio engine parameters.
    Injects completely missing BK N_Audio types, custom struct fields,
    and resolves Clang 15 strictness across the sequence player.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Existing Pull Function Signatures (Safeguard)
    content = content.replace(
        "extern Acmd *n_alAdpcmPull(s32, Acmd *);",
        "extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alEnvmixerPull(s32, Acmd *);",
        "extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alResamplePull(s32, Acmd *);",
        "extern Acmd *n_alResamplePull(N_PVoice *, s16 *, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alResamplePull(void *, s32, Acmd *);",
        "extern Acmd *n_alResamplePull(N_PVoice *, s16 *, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alFxPull(s32, Acmd *);",
        "extern Acmd *n_alFxPull(void);"
    )

    # 2. Append entirely missing root structs and macros
    missing_structs = """
#ifndef BK_AUDIO_PATCHES
#define BK_AUDIO_PATCHES

typedef struct ALPlayer_s {
    struct ALPlayer_s *next;
    void *clientData;
    void (*handler)(void *);
    s64 callTime;
    s32 samplesLeft;
} ALPlayer;

typedef struct N_ALEventListItem_s {
    struct N_ALEventListItem_s *next;
    struct N_ALEventListItem_s *prev;
    ALEvent event;
} N_ALEventListItem;

typedef ALGlobals N_ALGlobals;
typedef N_ALSyn N_ALSynth;

typedef struct ALEndEvent_s {
    s16 type;
    u32 ticks;
    u8 status;
    u8 len;
} ALEndEvent;

typedef struct ALLoopEvent_s {
    s16 type;
    u8 *start;
    u8 *end;
    s32 count;
} ALLoopEvent;

#define AL_SEQP_LOOP_EVT 0x80
#define AL_MIDI_FX_CTRL_0 0x81
#define AL_MIDI_FX_CTRL_1 0x82
#define AL_MIDI_FX_CTRL_2 0x83
#define AL_MIDI_FX_CTRL_3 0x84

#endif // BK_AUDIO_PATCHES
"""
    if "BK_AUDIO_PATCHES" not in content:
        content += missing_structs

    # 3. Inject missing custom fields into existing incomplete structs via Regex
    if "sv_dramout;" not in content:
        content = re.sub(r'\}\s*N_ALSyn;', '    s32 sv_dramout;\n    s32 curSamples;\n    ALPlayer *head;\n    ALPlayer *n_sndp;\n} N_ALSyn;', content)

    if "loopStart;" not in content:
        content = re.sub(r'\}\s*ALCSPlayer;', '    u8 *loopStart;\n    u8 *loopEnd;\n    s32 loopCount;\n} ALCSPlayer;', content)

    if "trackStart;" not in content:
        content = re.sub(r'\}\s*ALCSeq;', '    u8 *trackStart;\n    u8 *curPtr;\n    u8 lastStatus;\n} ALCSeq;', content)

    if "s32 curTicks;" not in content:
        content = re.sub(r'\}\s*ALCSeqMarker;', '    u8 *curPtr;\n    u8 lastStatus;\n    s32 curTicks;\n} ALCSeqMarker;', content)

    if "u32 ticks;" not in content:
        content = re.sub(r'\}\s*ALTempoEvent;', '    u32 ticks;\n    u32 len;\n} ALTempoEvent;', content)

    if "ALEndEvent end;" not in content:
        content = re.sub(r'(ALTempoEvent\s+tempo;)', r'\1\n    ALEndEvent end;\n    ALLoopEvent loop;', content)

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: BK Custom Audio Engine structs heavily injected.")

    # 4. Reverb implicit call fix (Maintained)
    reverb_path = 'src/core1/audio/n_reverb.c'
    if os.path.exists(reverb_path):
        with open(reverb_path, 'r') as f:
            reverb_content = f.read()
        if "ptr = n_alAuxBusPull();" in reverb_content:
            reverb_content = reverb_content.replace(
                "ptr = n_alAuxBusPull();", 
                "ptr = n_alAuxBusPull(0, ptr);"
            )
            with open(reverb_path, 'w') as f:
                f.write(reverb_content)
            print("✅ n_reverb.c patched: Fixed implicit n_alAuxBusPull arguments.")

if __name__ == '__main__':
    patch_audio_engine()
