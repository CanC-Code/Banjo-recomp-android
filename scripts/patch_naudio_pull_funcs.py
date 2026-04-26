import os
import re

def patch_naudio_pull_funcs():
    """
    Banjo-Kazooie Source-Specific Audio Sync.
    Aligns header signatures to the actual (inconsistent) source definitions.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("🧹 Scrubbing all conflicting n_audio prototypes...")
    conflict_pattern = r'extern\s+Acmd\s+\*\s*n_al(?:Fx|Envmixer|Adpcm|Resample|AuxBus|MainBus|Save)Pull\s*\([^;]*\);'
    content = re.sub(conflict_pattern, '', content)

    # Note: We use void* for Resample/Envmixer to stay compatible with N_PVoice types
    pull_funcs = """
#ifndef BKA_NAUDIO_PULL_FUNCS_DEFINED
#define BKA_NAUDIO_PULL_FUNCS_DEFINED

#ifdef __cplusplus
extern "C" {
#endif

/* Banjo-Recomp Verified Audio Signatures */
extern Acmd *n_alAdpcmPull(void *filter, s16 *outp, s32 outCount, Acmd *p); 
extern Acmd *n_alResamplePull(void *filter, s16 *outp, Acmd *p);            
extern Acmd *n_alEnvmixerPull(void *filter, s32 sampleOffset, Acmd *p);    
extern Acmd *n_alSavePull(s32 sampleOffset, Acmd *p);                      /* 2-arg */
extern Acmd *n_alAuxBusPull();                                             /* 0-arg for reverb.c compatibility */
extern Acmd *n_alFxPull();                                                  /* 0-arg */
extern Acmd *n_alMainBusPull();                                            /* 0-arg */

#ifdef __cplusplus
}
#endif

#endif /* BKA_NAUDIO_PULL_FUNCS_DEFINED */
"""
    # Inject before the final endif
    last_endif_idx = content.rfind('#endif')
    content = content[:last_endif_idx] + pull_funcs + "\n" + content[last_endif_idx:]

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Audio signatures synchronized to source definitions.")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
