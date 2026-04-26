import os

def patch_alglobals():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): 
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # If already defined by fix_n64_types.py or a previous run, skip.
    if "BKA_ALGLOBALS_DEFINED" in content:
        print("✅ ALGlobals already handled. Skipping.")
        return

    struct_def = """
/* =========================
   BANJO-SPECIFIC AUDIO STRUCTS
   ========================= */
#ifndef BKA_ALSYNTH_DEFINED
#define BKA_ALSYNTH_DEFINED
typedef struct ALSynth_s { u8 opaque_pad[256]; } ALSynth;
typedef ALSynth ALSyn; /* Fulfill legacy SDK alias requirements */
#endif

#ifndef BKA_ALGLOBALS_DEFINED
#define BKA_ALGLOBALS_DEFINED
typedef struct ALGlobals_s {
    ALSynth drvr;
    u8 pad[2048];
} ALGlobals;
#endif
"""
    # Insert before the last endif to keep the master guard intact
    last_endif = content.rfind('#endif')
    
    if last_endif != -1:
        new_content = content[:last_endif] + struct_def + "\n" + content[last_endif:]
    else:
        new_content = content + struct_def

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print("✅ Applied ALGlobals patch (with legacy ALSyn alias support).")

if __name__ == '__main__':
    patch_alglobals()
