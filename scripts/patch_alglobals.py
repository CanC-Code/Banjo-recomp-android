import os

def patch_alglobals():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path):
        print(f"File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # Ensure we haven't already patched it
    if "typedef struct ALGlobals_s" not in content and "ALGlobals;" not in content:
        
        # We know it needs the audio driver. 
        # We add a padding buffer to ensure the dynamic allocation size is large enough 
        # for any remaining undocumented engine audio variables.
        struct_def = """
/* ALGlobals definition injected for NativeBridge and stubs */
typedef struct ALGlobals_s {
    ALSynth drvr;
    u8 pad[2048]; /* Padding to ensure adequate allocation size */
} ALGlobals;
"""
        # Find the final #endif (the include guard closer) and insert right before it
        last_endif_idx = content.rfind('#endif')
        
        if last_endif_idx != -1:
            content = content[:last_endif_idx] + struct_def + "\n" + content[last_endif_idx:]
        else:
            # Fallback if no #endif is found, though our previous script fixed this
            content += struct_def

        with open(header_path, 'w') as f:
            f.write(content)
        print("✅ n64_types.h successfully patched with ALGlobals definition.")
    else:
        print("✅ ALGlobals is already defined.")

if __name__ == '__main__':
    patch_alglobals()
