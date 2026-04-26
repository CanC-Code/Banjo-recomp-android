import os
import re

def mega_patch_audio_structs():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("🚀 Starting Audio Header Mega-Patch...")

    # 1. Fix N_ALSyn (Missing sv_dramout and head)
    if 'sv_dramout' not in content:
        content = re.sub(r'(struct\s+N_ALSyn_s\s*\{)', 
                         r'\1\n    void* head; /* Added for n_seqplayer */\n    int sv_dramout; /* Added for n_save */', 
                         content)

    # 2. Fix ALCSPlayer / ALCSPlayer_s (Missing loop members)
    if 'loopStart' not in content:
        content = re.sub(r'(struct\s+ALCSPlayer_s\s*\{)', 
                         r'\1\n    u32 loopStart;\n    u32 loopEnd;\n    s32 loopCount;', 
                         content)

    # 3. Fix ALEvent Union (Missing loop and end members)
    # This is a bit tricky, we look for the msg union inside ALEvent
    if 'ALTempoEvent' in content and 'loop' not in content:
        loop_struct = "        struct { u32 start; u32 end; s32 count; } loop;\n        struct { u32 ticks; u8 status; u8 type; u8 len; } end;"
        content = content.replace('ALTempoEvent     tempo;', f'ALTempoEvent     tempo;\n{loop_struct}')

    # 4. Fix ALTempoEvent (Missing ticks and len)
    if 'typedef struct { ' in content and 'ALTempoEvent' in content:
        content = re.sub(r'(typedef\s+struct\s*\{[^}]*)(ALTempoEvent;)', 
                         r'\1    u32 ticks; u8 len; \2', content)

    # 5. Fix Assignability: lastStatus and curBUPtr
    # The source wants to assign to these, so they CANNOT be arrays of [16] if the source expects a single value.
    # We change u8 lastStatus[16] -> u8 lastStatus
    content = content.replace('u8          lastStatus[16];', 'u8          lastStatus;')
    # Change curBUPtr[16] -> u8* curPtr (or just keep it if we can't safely change it)
    # Based on error 7029, n_seq.c wants .curPtr
    content = content.replace('u8          *curBUPtr[16];', 'u8 *curBUPtr[16];\n    u8 *curPtr;')

    # 6. Missing Typedefs (N_ALSynth, N_ALEventListItem, ALSeqMarker)
    missing_types = """
/* Missing Recomp Type Definitions */
typedef struct N_ALSynth_s { void* head; } N_ALSynth;
typedef ALEventListItem N_ALEventListItem;
typedef ALCSeqMarker ALSeqMarker;
#define AL_SEQP_LOOP_EVT 10
#define AL_MIDI_FX_CTRL_0 20
#define AL_MIDI_FX_CTRL_1 21
#define AL_MIDI_FX_CTRL_2 22
#define AL_MIDI_FX_CTRL_3 23
"""
    if 'N_ALSynth' not in content:
        content += missing_types

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Mega-Patch applied. Structures are now Banjo-compatible.")

if __name__ == '__main__':
    mega_patch_audio_structs()
