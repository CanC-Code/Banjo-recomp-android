import os

def patch_alglobals():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r') as f:
        content = f.read()

    # If already defined by fix_n64_types.py or a previous run, skip.
    if "BKA_ALGLOBALS_DEFINED" in content:
        print("✅ ALGlobals already handled. Skipping.")
        return

    struct_def = """
#ifndef BKA_ALSYNTH_DEFINED
#define BKA_ALSYNTH_DEFINED
typedef struct { u8 opaque_pad[256]; } ALSynth;
#endif

#ifndef BKA_ALGLOBALS_DEFINED
#define BKA_ALGLOBALS_DEFINED
typedef struct ALGlobals_s {
    ALSynth drvr;
    u8 pad[2048];
} ALGlobals;
#endif
"""
    # Insert before the last endif
    last_endif = content.rfind('#endif')
    new_content = content[:last_endif] + struct_def + "\n" + content[last_endif:]
    
    with open(header_path, 'w') as f:
        f.write(new_content)
    print("✅ Applied ALGlobals patch.")

if __name__ == '__main__':
    patch_alglobals()
