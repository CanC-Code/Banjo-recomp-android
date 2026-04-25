import os
import re

def patch_audio_engine():
    """
    Comprehensive patch for Banjo-Kazooie audio engine.
    1. Restores multi-track arrays in ALCSeq structs.
    2. Corrects n_audio Pull function prototypes to match BK's custom signatures.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # --- PART 1: Restoring Struct Arrays (from previous fix) ---
    bk_struct_fields = "    u8 lastStatus[16];\n    u8 *curBUPtr[16];\n"

    def apply_struct_patch(text, struct_name):
        pattern = r'(struct\s+\w*?' + struct_name + r'.*?\{)(.*?)(\}\s*' + struct_name + r'?;)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            header, body, footer = match.groups()
            body = re.sub(r'.*lastStatus.*;\n?', '', body)
            body = re.sub(r'.*curBUPtr.*;\n?', '', body)
            body = re.sub(r'.*curPtr.*;\n?', '', body)
            new_body = body.rstrip() + "\n" + bk_struct_fields
            return text[:match.start()] + header + new_body + footer + text[match.end():]
        return text

    content = apply_struct_patch(content, "ALCSeq")
    content = apply_struct_patch(content, "ALCSeqMarker")

    # --- PART 2: Correcting Function Prototypes ---
    # These replacements ensure the header matches the calls in n_auxbus.c and n_adpcm.c
    
    # 1. n_alEnvmixerPull: Needs (void*, s32, Acmd*)
    content = re.sub(
        r'extern\s+Acmd\s+\*n_alEnvmixerPull\(s32,\s+Acmd\s+\*\);',
        r'extern Acmd *n_alEnvmixerPull(void *, s32, Acmd *);',
        content
    )

    # 2. n_alAdpcmPull: Needs (void*, s16*, s32, Acmd*)
    content = re.sub(
        r'extern\s+Acmd\s+\*n_alAdpcmPull\(s32,\s+Acmd\s+\*\);',
        r'extern Acmd *n_alAdpcmPull(void *, s16 *, s32, Acmd *);',
        content
    )

    # 3. n_alResamplePull: Needs (void*, s32, Acmd*) - Proactive fix for next likely error
    content = re.sub(
        r'extern\s+Acmd\s+\*n_alResamplePull\(s32,\s+Acmd\s+\*\);',
        r'extern Acmd *n_alResamplePull(void *, s32, Acmd *);',
        content
    )

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h patched: Structs restored and function prototypes corrected for BK audio engine.")

if __name__ == '__main__':
    patch_audio_engine()
