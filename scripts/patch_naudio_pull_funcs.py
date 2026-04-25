import os

def patch_naudio_signatures():
    """
    Corrects the specific n_al...Pull function signatures to match the C 
    implementation arguments required by the Banjo-Kazooie N_Audio engine.
    Applies the necessary changes to a fresh baseline.
    """
    file_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(file_path):
        print(f"❌ Error: {file_path} not found. Ensure fix_n64_types.py ran first.")
        return

    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Fix the ADPCM signature (4 args expected)
    # Matches the implementation in src/core1/audio/n_adpcm.c
    content = content.replace(
        "extern Acmd *n_alAdpcmPull(s32, Acmd *);",
        "extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);"
    )
    
    # 2. Fix the EnvMixer signature (3 args expected)
    # Matches the implementation called in src/core1/audio/n_auxbus.c
    content = content.replace(
        "extern Acmd *n_alEnvmixerPull(s32, Acmd *);",
        "extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);"
    )

    # 3. Fix the Resample signature (3 args expected)
    # Matches the implementation called in src/core1/audio/n_env.c
    content = content.replace(
        "extern Acmd *n_alResamplePull(s32, Acmd *);",
        "extern Acmd *n_alResamplePull(void *, s32, Acmd *);"
    )

    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: N_Audio ADPCM, EnvMixer, and Resample function signatures correctly realigned.")

if __name__ == '__main__':
    patch_naudio_signatures()
