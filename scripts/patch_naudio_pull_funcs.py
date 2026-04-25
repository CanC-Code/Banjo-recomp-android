import os

def patch_audio_engine():
    """
    Comprehensive patch for the N_Audio engine parameters.
    Addresses N_ALSyn struct missing members, remaining function signature
    mismatches, and a legacy implicit argument call in n_reverb.c.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if os.path.exists(header_path):
        with open(header_path, 'r') as f:
            content = f.read()

        # 1. Fix the ADPCM signature
        content = content.replace(
            "extern Acmd *n_alAdpcmPull(s32, Acmd *);",
            "extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);"
        )
        
        # 2. Fix the EnvMixer signature
        content = content.replace(
            "extern Acmd *n_alEnvmixerPull(s32, Acmd *);",
            "extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);"
        )

        # 3. Fix the Resample signature (Matches N_PVoice*, s16*, Acmd*)
        content = content.replace(
            "extern Acmd *n_alResamplePull(s32, Acmd *);",
            "extern Acmd *n_alResamplePull(N_PVoice *, s16 *, Acmd *);"
        )
        # Fallback for previous patch attempt
        content = content.replace(
            "extern Acmd *n_alResamplePull(void *, s32, Acmd *);",
            "extern Acmd *n_alResamplePull(N_PVoice *, s16 *, Acmd *);"
        )

        # 4. Fix the FxPull signature (Takes void)
        content = content.replace(
            "extern Acmd *n_alFxPull(s32, Acmd *);",
            "extern Acmd *n_alFxPull(void);"
        )

        # 5. Inject the missing 'sv_dramout' into the N_ALSyn struct
        if "sv_dramout;" not in content:
            content = content.replace("} N_ALSyn;", "    s32 sv_dramout;\n} N_ALSyn;")

        with open(header_path, 'w') as f:
            f.write(content)
        print("✅ n64_types.h patched: Signatures and N_ALSyn struct fully aligned.")
    else:
        print(f"❌ Error: {header_path} not found.")

    # 6. Fix legacy 0-argument call in n_reverb.c
    reverb_path = 'src/core1/audio/n_reverb.c'
    if os.path.exists(reverb_path):
        with open(reverb_path, 'r') as f:
            reverb_content = f.read()
        
        # The modern compiler caught `ptr = n_alAuxBusPull();` missing arguments.
        # We supply the standard N_Audio auxbus arguments: (sampleOffset, Acmd *p)
        if "ptr = n_alAuxBusPull();" in reverb_content:
            reverb_content = reverb_content.replace(
                "ptr = n_alAuxBusPull();", 
                "ptr = n_alAuxBusPull(0, ptr);"
            )
            with open(reverb_path, 'w') as f:
                f.write(reverb_content)
            print("✅ n_reverb.c patched: Fixed implicit n_alAuxBusPull arguments.")

if __name__ == '__main__':
    patch_audio_engine()
