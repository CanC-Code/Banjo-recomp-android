import os
import re

def patch_naudio_pull_funcs():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("🧹 Cleaning old n_audio pull prototypes...")
    conflict_pattern = r'extern\s+Acmd\s+\*\s*n_al(?:Fx|Envmixer|Adpcm|Resample|AuxBus|MainBus|Save)Pull\s*\([^;]*\);'
    content = re.sub(conflict_pattern, '', content)

    pull_funcs = """
#ifndef BKA_NAUDIO_PULL_FUNCS_DEFINED
#define BKA_NAUDIO_PULL_FUNCS_DEFINED

#ifdef __cplusplus
extern "C" {
#endif

/* Banjo-Recomp Absolute Verified Signatures */
/* Note: Using N_PVoice* specifically to match n_resample.c:11 */
typedef struct N_PVoice_s N_PVoice; 

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

#endif /* BKA_NAUDIO_PULL_FUNCS_DEFINED */
"""
    last_endif_idx = content.rfind('#endif')
    content = content[:last_endif_idx] + pull_funcs + "\n" + content[last_endif_idx:]

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Audio signatures updated with N_PVoice types.")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
