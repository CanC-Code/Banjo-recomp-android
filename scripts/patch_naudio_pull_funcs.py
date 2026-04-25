import os
import re

def patch_audio_engine():
    """
    Comprehensive patch for the N_Audio engine parameters.
    Fixes 'unknown type name' errors by using fundamental C primitive types
    in the top-level struct declarations, completely avoiding dependency 
    on Libultra typedefs being parsed beforehand.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Existing Pull Function Signatures
    content = content.replace("extern Acmd *n_alAdpcmPull(s32, Acmd *);", "extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);")
    content = content.replace("extern Acmd *n_alEnvmixerPull(s32, Acmd *);", "extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);")
    content = content.replace("extern Acmd *n_alResamplePull(s32, Acmd *);", "extern Acmd *n_alResamplePull(N_PVoice *, s16 *, Acmd *);")
    content = content.replace("extern Acmd *n_alResamplePull(void *, s32, Acmd *);", "extern Acmd *n_alResamplePull(N_PVoice *, s16 *, Acmd *);")
    content = content.replace("extern Acmd *n_alFxPull(s32, Acmd *);", "extern Acmd *n_alFxPull(void);")

    # 2. Top-level missing structs using fundamental C types
    top_structs = """
#ifndef BK_AUDIO_PATCHES_TOP
#define BK_AUDIO_PATCHES_TOP

typedef struct ALPlayer_s {
    struct ALPlayer_s *next;
    void *clientData;
    void (*handler)(void *);
    long long callTime;    // Maps to s64
    int samplesLeft;       // Maps to s32
} ALPlayer;

typedef struct ALEndEvent_s {
    short type;            // Maps to s16
    unsigned int ticks;    // Maps to u32
    unsigned char status;  // Maps to u8
    unsigned char len;     // Maps to u8
} ALEndEvent;

typedef struct ALLoopEvent_s {
    short type;            // Maps to s16
    unsigned char *start;  // Maps to u8*
    unsigned char *end;    // Maps to u8*
    int count;             // Maps to s32
} ALLoopEvent;

#define AL_SEQP_LOOP_EVT 0x80
#define AL_MIDI_FX_CTRL_0 0x81
#define AL_MIDI_FX_CTRL_1 0x82
#define AL_MIDI_FX_CTRL_2 0x83
#define AL_MIDI_FX_CTRL_3 0x84

#endif // BK_AUDIO_PATCHES_TOP
"""

    # Remove previous top_structs injection if it exists to allow clean replacement
    content = re.sub(r'#ifndef BK_AUDIO_PATCHES_TOP.*?#endif // BK_AUDIO_PATCHES_TOP', '', content, flags=re.DOTALL)

    # Hoist dependencies to the top of the file
    if "#define _N64_TYPES_H_" in content:
        content = content.replace("#define _N64_TYPES_H_", "#define _N64_TYPES_H_\n" + top_structs)
    else:
        content = top_structs + "\n" + content

    # 3. Bottom-level missing structs
    bottom_structs = """
#ifndef BK_AUDIO_PATCHES_BOTTOM
#define BK_AUDIO_PATCHES_BOTTOM

typedef struct N_ALEventListItem_s {
    struct N_ALEventListItem_s *next;
    struct N_ALEventListItem_s *prev;
    ALEvent event;
} N_ALEventListItem;

typedef ALGlobals N_ALGlobals;
typedef N_ALSyn N_ALSynth;

#endif // BK_AUDIO_PATCHES_BOTTOM
"""
    if "BK_AUDIO_PATCHES_BOTTOM" not in content:
        content += bottom_structs

    # 4. Clean residual generic Libultra arrays
    content = re.sub(r'u8\s+lastStatus\[16\];', '// removed lastStatus array', content)
    content = re.sub(r'u8\s*\*\s*curBUPtr\[16\];', '// removed curBUPtr array', content)

    # 5. Inject custom Banjo-Kazooie fields using primitive types to match top declarations
    if "sv_dramout;" not in content:
        content = re.sub(r'\}\s*N_ALSyn;', '    int sv_dramout;\n    int curSamples;\n    ALPlayer *head;\n    ALPlayer *n_sndp;\n} N_ALSyn;', content)

    if "loopStart;" not in content:
        content = re.sub(r'\}\s*ALCSPlayer;', '    unsigned char *loopStart;\n    unsigned char *loopEnd;\n    int loopCount;\n} ALCSPlayer;', content)

    if "unsigned char *trackStart;" not in content and "u8 *trackStart;" not in content:
        content = re.sub(r'\}\s*ALCSeq;', '    unsigned char *trackStart;\n    unsigned char *curPtr;\n    unsigned char lastStatus;\n} ALCSeq;', content)

    if "curTicks;" not in content:
        content = re.sub(r'\}\s*ALCSeqMarker;', '    unsigned char *curPtr;\n    unsigned char lastStatus;\n    int curTicks;\n} ALCSeqMarker;', content)

    if "ALEndEvent end;" not in content:
        content = re.sub(r'(ALTempoEvent\s+tempo;)', r'\1\n    ALEndEvent end;\n    ALLoopEvent loop;', content)

    if "unsigned int ticks;" not in content and "u32 ticks;" not in content:
        content = re.sub(r'\}\s*ALTempoEvent;', '    unsigned int ticks;\n    unsigned char len;\n} ALTempoEvent;', content)

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: Primitive C types used to avoid declaration ordering issues.")

    # 6. Reverb implicit call fix (Maintained)
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
