import os

def patch_naudio_signatures():
    """
    Sister script to modify n64_types.h inline.
    Corrects the specific n_al...Pull function signatures to match the C 
    implementation arguments required by the Banjo-Kazooie N_Audio engine.
    """
    file_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(file_path):
        print(f"❌ Error: {file_path} not found. Ensure fix_n64_types.py ran first.")
        return

    with open(file_path, 'r') as f:
        content = f.read()

    # 1. Fix the explicitly failing ADPCM signature (4 args expected)
    content = content.replace(
        "extern Acmd *n_alAdpcmPull(s32, Acmd *);",
        "extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);"
    )
    
    # 2. Fix the explicitly failing EnvMixer signature (3 args expected)
    content = content.replace(
        "extern Acmd *n_alEnvmixerPull(s32, Acmd *);",
        "extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);"
    )
    
    # 3. Preemptively correct the remaining N_Audio pull routines to include 
    # their filter context pointers (void *) to prevent subsequent halts.
    content = content.replace(
        "extern Acmd *n_alResamplePull(s32, Acmd *);",
        "extern Acmd *n_alResamplePull(void *, s32, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alAuxBusPull(s32, Acmd *);",
        "extern Acmd *n_alAuxBusPull(void *, s32, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alMainBusPull(s32, Acmd *);",
        "extern Acmd *n_alMainBusPull(void *, s32, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alFxPull(s32, Acmd *);",
        "extern Acmd *n_alFxPull(void *, s32, Acmd *);"
    )
    content = content.replace(
        "extern Acmd *n_alSavePull(s32, Acmd *);",
        "extern Acmd *n_alSavePull(void *, s32, Acmd *);"
    )

    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: N_Audio pull function signatures securely realigned.")

if __name__ == '__main__':
    patch_naudio_signatures()
