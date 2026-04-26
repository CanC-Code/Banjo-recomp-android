import os
import re

def banjo_structural_harmony():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): 
        print(f"❌ {header_path} not found.")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("🚀 Harmonizing Headers for Banjo-Kazooie...")

    # 1. APPLY GLOBAL INCLUDE GUARDS
    if '#ifndef BANJO_RECOMP_N64_TYPES_H' not in content:
        content = "#ifndef BANJO_RECOMP_N64_TYPES_H\n#define BANJO_RECOMP_N64_TYPES_H\n#pragma once\n\n" + content + "\n#endif"

    # 2. SCRUB CONFLICTING PROTOTYPES (The "Search & Destroy")
    # This removes the generic 'extern Acmd *n_al...Pull(...);' declarations that cause conflicts
    pull_names = ['Adpcm', 'Resample', 'Envmixer', 'AuxBus', 'Fx', 'MainBus', 'Save']
    for name in pull_names:
        # Matches 'extern Acmd *n_alNamePull(...);' regardless of parameter types
        pattern = rf'extern\s+Acmd\s+\*\s*n_al{name}Pull\s*\([^;]*\);'
        content = re.sub(pattern, f'/* Removed generic n_al{name}Pull */', content)

    # 3. FIX STRUCT: N_ALSyn (Add 'head' and 'sv_dramout')
    if 'sv_dramout' not in content:
        content = re.sub(r'(struct\s+N_ALSyn_s\s*\{)', 
                         r'\1\n    void* head;\n    int sv_dramout;', content)

    # 4. FIX STRUCT: ALCSPlayer (Add loop members)
    if 'loopStart' not in content:
        content = re.sub(r'(struct\s+ALCSPlayer_s\s*\{)', 
                         r'\1\n    u32 loopStart;\n    u32 loopEnd;\n    s32 loopCount;', content)

    # 5. FIX UNION: ALEvent (Add 'loop' and 'end' struct support)
    if 'ALTempoEvent' in content and 'loop' not in content:
        event_structs = "        struct { u32 start; u32 end; s32 count; } loop;\n        struct { u32 ticks; u8 status; u8 type; u8 len; } end;"
        content = content.replace('ALTempoEvent     tempo;', f'ALTempoEvent     tempo;\n{event_structs}')

    # 6. FIX STRUCT: ALTempoEvent (Add ticks/len)
    if 'typedef struct { ' in content and 'ALTempoEvent' in content:
        content = re.sub(r'(typedef\s+struct\s*\{[^}]*)(ALTempoEvent;)', r'\1    u32 ticks; u8 len; \2', content)

    # 7. FIX ASSIGNABILITY (Arrays vs Bytes)
    content = content.replace('u8          lastStatus[16];', 'u8          lastStatus;')
    if 'u8 *curPtr;' not in content:
        content = content.replace('u8          *curBUPtr[16];', 'u8 *curBUPtr[16];\n    u8 *curPtr;')

    # 8. INJECT BANJO-SPECIFIC DEFINITIONS & PROTOTYPES
    banjo_defs = """
/* Banjo-Kazooie N_Audio definitions */
typedef struct N_ALSynth_s { void* head; } N_ALSynth;
typedef ALEventListItem N_ALEventListItem;
typedef ALCSeqMarker ALSeqMarker;
#define AL_SEQP_LOOP_EVT 10
#define AL_MIDI_FX_CTRL_0 20
#define AL_MIDI_FX_CTRL_1 21
#define AL_MIDI_FX_CTRL_2 22
#define AL_MIDI_FX_CTRL_3 23

#ifdef __cplusplus
extern "C" {
#endif
extern Acmd *n_alAdpcmPull(void *filter, s16 *outp, s32 outCount, Acmd *p); 
extern Acmd *n_alResamplePull(N_PVoice *filter, s16 *outp, Acmd *p);            
extern Acmd *n_alEnvmixerPull(void *filter, s32 sampleOffset, Acmd *p);    
extern Acmd *n_alSavePull(s32 sampleOffset, Acmd *p);
extern Acmd *n_alAuxBusPull(); 
extern Acmd *n_alFxPull();     
extern Acmd *n_alMainBusPull();
#ifdef __cplusplus
}
#endif
"""
    # Insert before the final #endif
    content = content.replace('\n#endif', banjo_defs + '\n#endif')

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Header Harmonized. Conflicting generic types removed.")

if __name__ == '__main__':
    banjo_structural_harmony()
