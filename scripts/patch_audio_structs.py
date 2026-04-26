import os
import re

def apply_mega_patch():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): 
        print(f"❌ {header_path} not found.")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("🚀 Applying Structural Overhaul & Include Guards...")

    # 1. ADD HEADER GUARDS (Fixes the Redefinition Error)
    if '#ifndef BANJO_RECOMP_N64_TYPES_H' not in content:
        content = "#ifndef BANJO_RECOMP_N64_TYPES_H\n#define BANJO_RECOMP_N64_TYPES_H\n#pragma once\n\n" + content + "\n#endif /* BANJO_RECOMP_N64_TYPES_H */"

    # 2. Fix N_ALSyn (Add 'head' and 'sv_dramout' members)
    if 'sv_dramout' not in content:
        # Match 'struct N_ALSyn_s {' and inject members at the start of the struct
        content = re.sub(r'(struct\s+N_ALSyn_s\s*\{)', 
                         r'\1\n    void* head; /* Required for n_seqplayer */\n    int sv_dramout; /* Required for n_save */', 
                         content)

    # 3. Fix ALCSPlayer (Add missing loop management members)
    if 'loopStart' not in content:
        content = re.sub(r'(struct\s+ALCSPlayer_s\s*\{)', 
                         r'\1\n    u32 loopStart;\n    u32 loopEnd;\n    s32 loopCount;', 
                         content)

    # 4. Fix ALEvent Union (Inject 'loop' and 'end' sub-structs)
    if 'ALTempoEvent' in content and 'loop' not in content:
        loop_struct = "        struct { u32 start; u32 end; s32 count; } loop;\n        struct { u32 ticks; u8 status; u8 type; u8 len; } end;"
        content = content.replace('ALTempoEvent     tempo;', f'ALTempoEvent     tempo;\n{loop_struct}')

    # 5. Fix ALTempoEvent definition (Add ticks and len)
    if 'typedef struct { ' in content and 'ALTempoEvent' in content:
        content = re.sub(r'(typedef\s+struct\s*\{[^}]*)(ALTempoEvent;)', 
                         r'\1    u32 ticks; u8 len; \2', content)

    # 6. Fix Variable Types (Change arrays to single assignable values)
    # n_seq.c expects lastStatus to be a simple byte, not a [16] array
    content = content.replace('u8          lastStatus[16];', 'u8          lastStatus;')
    
    # Add curPtr support for n_seq.c logic
    if 'u8 *curPtr;' not in content:
        content = content.replace('u8          *curBUPtr[16];', 'u8 *curBUPtr[16];\n    u8 *curPtr;')

    # 7. Add Missing Type Aliases & Constants (Inside the guard)
    extra_defs = """
/* Banjo-Specific Definitions */
#ifndef BKA_EXTRA_DEFS
#define BKA_EXTRA_DEFS
typedef struct N_ALSynth_s { void* head; } N_ALSynth;
typedef ALEventListItem N_ALEventListItem;
typedef ALCSeqMarker ALSeqMarker;
#define AL_SEQP_LOOP_EVT 10
#define AL_MIDI_FX_CTRL_0 20
#define AL_MIDI_FX_CTRL_1 21
#define AL_MIDI_FX_CTRL_2 22
#define AL_MIDI_FX_CTRL_3 23
#endif
"""
    # Insert extra defs before the final #endif
    last_endif_pos = content.rfind('#endif /* BANJO_RECOMP_N64_TYPES_H */')
    content = content[:last_endif_pos] + extra_defs + content[last_endif_pos:]

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Header is now guarded and structural members injected.")

if __name__ == '__main__':
    apply_mega_patch()
