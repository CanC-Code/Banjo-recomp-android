import os
import re

def patch_naudio_pull_funcs():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean old ones first
    conflict_pattern = r'extern\s+Acmd\s+\*\s*n_al(?:Fx|Envmixer|Adpcm|Resample|AuxBus|MainBus|Save)Pull\s*\([^;]*\);'
    content = re.sub(conflict_pattern, '', content)

    # Note: Using N_PVoice (which is an alias for ALPVoice in your header)
    pull_funcs = """
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
    content += pull_funcs

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Audio signatures synchronized.")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
