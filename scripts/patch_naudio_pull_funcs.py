import os

def patch_naudio_pull_funcs():
    """
    Additive patcher for n_audio HLE pull functions.
    Updated to match the 4-argument signatures used in the Banjo source.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # If this specific guard exists, we've already patched this file.
    if "BKA_NAUDIO_PULL_FUNCS_DEFINED" in content:
        print("✅ n_audio pull functions already present. Skipping.")
        return

    # Prototype block for n_audio (Next-Gen) engine functions
    # Using the standard 4-arg signature: (void *filter, s16 *outp, s32 outCount, Acmd *p)
    pull_funcs = """
#ifndef BKA_NAUDIO_PULL_FUNCS_DEFINED
#define BKA_NAUDIO_PULL_FUNCS_DEFINED

#ifdef __cplusplus
extern "C" {
#endif

/* HLE Audio Processing Prototypes (Standard 4-arg signatures) */
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

    # Inject right before the final #endif
    last_endif_idx = content.rfind('#endif')
    if last_endif_idx != -1:
        content = content[:last_endif_idx] + pull_funcs + "\n" + content[last_endif_idx:]
    else:
        content += pull_funcs

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ Successfully updated n_audio pull signatures in n64_types.h")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
