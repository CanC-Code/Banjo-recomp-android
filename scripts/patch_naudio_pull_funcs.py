import os

def patch_naudio_pull_funcs():
    """
    Additive patcher for n_audio HLE pull functions.
    Does not delete existing types; only ensures function prototypes exist.
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
    # These are often missing from standard libultra headers but required by Banjo
    pull_funcs = """
#ifndef BKA_NAUDIO_PULL_FUNCS_DEFINED
#define BKA_NAUDIO_PULL_FUNCS_DEFINED

#ifdef __cplusplus
extern "C" {
#endif

/* HLE Audio Processing Prototypes */
extern Acmd *n_alFxPull(s32, Acmd *);
extern Acmd *n_alEnvmixerPull(s32, Acmd *);
extern Acmd *n_alAdpcmPull(s32, Acmd *);
extern Acmd *n_alResamplePull(s32, Acmd *);
extern Acmd *n_alAuxBusPull(s32, Acmd *);
extern Acmd *n_alMainBusPull(s32, Acmd *);
extern Acmd *n_alSavePull(s32, Acmd *);

#ifdef __cplusplus
}
#endif

#endif /* BKA_NAUDIO_PULL_FUNCS_DEFINED */
"""

    # We inject these right before the final #endif to ensure all types (Acmd, s32, etc.) are already known.
    last_endif_idx = content.rfind('#endif')
    if last_endif_idx != -1:
        content = content[:last_endif_idx] + pull_funcs + "\n" + content[last_endif_idx:]
    else:
        content += pull_funcs

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ Successfully added n_audio pull function prototypes to n64_types.h")

if __name__ == '__main__':
    patch_naudio_pull_funcs()
