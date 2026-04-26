import os
import re

def patch_naudio_pull_funcs():
    """
    Sanitizing patcher for n_audio HLE pull functions.
    Removes stale 2-arg declarations and replaces them with 4-arg signatures.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. SCRUBBING PHASE: Remove the old 2-argument declarations
    # This prevents the "conflicting types" error seen in the logs.
    print("🧹 Scrubbing stale n_audio 2-arg signatures...")
    old_sig_pattern = r'extern\s+Acmd\s+\*\s*n_al(?:Fx|Envmixer|Adpcm|Resample|AuxBus|MainBus|Save)Pull\s*\(\s*s32\s*,\s*Acmd\s*\*\s*\)\s*;'
    content = re.sub(old_sig_pattern, '', content)

    # If the cooperative guard is already there, we don't need to re-inject the new block
    if "BKA_NAUDIO_PULL_FUNCS_DEFINED" in content:
        # We still write back because we might have scrubbed old ones in this pass
        with open(header_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ Header sanitized and signatures verified.")
        return

    # 2. INJECTION PHASE: Add the standard 4-arg signatures
    pull_funcs = """
#ifndef BKA_NAUDIO_PULL_FUNCS_DEFINED
#define BKA_NAUDIO_PULL_FUNCS_DEFINED

#ifdef __cplusplus
extern "C" {
#endif

/* HLE Audio Processing Prototypes (Standard 4-arg signatures for Banjo) */
extern Acmd *n_alFxPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alEnvmixerPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alResamplePull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alAuxBusPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alMainBusPull(void *, s16 *, s32, Acmd *);
extern Acmd *n_alSavePull(void *, s16 *, s32, Acmd *);

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

    print("✅ Successfully synchronized n_audio signatures in n64_types.h")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
