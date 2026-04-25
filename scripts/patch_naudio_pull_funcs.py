import os

def revert_overpatched_signatures():
    """
    Sister script to modify n64_types.h inline.
    Reverts the bus, resample, and save N_Audio pull functions back to their 
    strict 2-argument signatures (s32, Acmd *) required by the C implementation, 
    while leaving the ADPCM and EnvMixer signatures intact.
    """
    file_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(file_path):
        print(f"❌ Error: {file_path} not found.")
        return

    with open(file_path, 'r') as f:
        content = f.read()

    # Safely revert the over-patched bus and effect pull routines back to the 2-arg signature
    replacements = [
        ("extern Acmd *n_alResamplePull(void *, s32, Acmd *);", "extern Acmd *n_alResamplePull(s32, Acmd *);"),
        ("extern Acmd *n_alAuxBusPull(void *, s32, Acmd *);", "extern Acmd *n_alAuxBusPull(s32, Acmd *);"),
        ("extern Acmd *n_alMainBusPull(void *, s32, Acmd *);", "extern Acmd *n_alMainBusPull(s32, Acmd *);"),
        ("extern Acmd *n_alFxPull(void *, s32, Acmd *);", "extern Acmd *n_alFxPull(s32, Acmd *);"),
        ("extern Acmd *n_alSavePull(void *, s32, Acmd *);", "extern Acmd *n_alSavePull(s32, Acmd *);")
    ]

    for old_sig, new_sig in replacements:
        if old_sig in content:
            content = content.replace(old_sig, new_sig)
        else:
            print(f"⚠️ Warning: Target signature not found: {old_sig}")

    with open(file_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: N_Audio bus and effect signatures reverted to 2-arguments.")

if __name__ == '__main__':
    revert_overpatched_signatures()
