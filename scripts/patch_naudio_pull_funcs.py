import os
import re

def patch_naudio_pull_funcs():
    """
    Synchronizes n_audio HLE pull functions with the Banjo-Recomp source.
    Scrubs all previous variations and injects the specific 2, 3, and 4-arg signatures.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. AGGRESSIVE SCRUBBING
    # This regex looks for any 'extern Acmd *n_al...Pull(...);' variation to clear the conflict.
    print("🧹 Clearing all conflicting n_audio prototypes...")
    conflict_pattern = r'extern\s+Acmd\s+\*\s*n_al(?:Fx|Envmixer|Adpcm|Resample|AuxBus|MainBus|Save)Pull\s*\([^;]*\);'
    content = re.sub(conflict_pattern, '', content)

    # 2. INJECTION OF BANJO-SPECIFIC SIGNATURES
    # These are derived directly from your build failure logs.
    pull_funcs = """
#ifndef BKA_NAUDIO_PULL_FUNCS_DEFINED
#define BKA_NAUDIO_PULL_FUNCS_DEFINED

#ifdef __cplusplus
extern "C" {
#endif

/* Banjo-Specific Hybrid Audio Prototypes */
extern Acmd *n_alAdpcmPull(void *filter, s16 *outp, s32 outCount, Acmd *p);    /* 4-arg */
extern Acmd *n_alResamplePull(void *filter, s16 *outp, Acmd *p);               /* 3-arg */
extern Acmd *n_alEnvmixerPull(void *filter, s32 sampleOffset, Acmd *p);       /* 3-arg */
extern Acmd *n_alAuxBusPull(s32 sampleOffset, Acmd *p);                       /* 2-arg */
extern Acmd *n_alFxPull(void *filter, s32 sampleOffset, Acmd *p);             /* 3-arg */
extern Acmd *n_alMainBusPull(s32 sampleOffset, Acmd *p);                      /* 2-arg */
extern Acmd *n_alSavePull(void *filter, s32 sampleOffset, Acmd *p);           /* 3-arg */

#ifdef __cplusplus
}
#endif

#endif /* BKA_NAUDIO_PULL_FUNCS_DEFINED */
"""

    last_endif_idx = content.rfind('#endif')
    if last_endif_idx != -1:
        content = content[:last_endif_idx] + pull_funcs + "\n" + content[last_endif_idx:]
    else:
        content += pull_funcs

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Successfully synchronized Banjo-Hybrid audio signatures.")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
