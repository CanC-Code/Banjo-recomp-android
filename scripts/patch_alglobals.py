import os
import re

def patch_alglobals_robustly():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Sanitize the header by removing any incomplete forward declarations 
    # that caused the previous script to yield a false positive.
    content = re.sub(r'typedef\s+struct\s+[a-zA-Z0-9_]+\s+ALGlobals\s*;\s*', '', content)
    content = re.sub(r'struct\s+ALGlobals\s*;\s*', '', content)

    # 2. Establish the concrete memory layout
    struct_def = """
#ifndef BKA_ALGLOBALS_DEFINED
#define BKA_ALGLOBALS_DEFINED

/* Defensively define ALSynth to prevent cascading undeclared type errors */
#ifndef BKA_ALSYNTH_DEFINED
#define BKA_ALSYNTH_DEFINED
typedef struct {
    u8 opaque_pad[256];
} ALSynth;
#endif

/* Concrete definition of ALGlobals required for sizeof() in memory allocation */
typedef struct ALGlobals_s {
    ALSynth drvr;
    u8 pad[2048]; /* Padding to ensure adequate allocation size for the audio engine */
} ALGlobals;

#endif /* BKA_ALGLOBALS_DEFINED */
"""

    # 3. Inject the complete struct prior to the final include guard closer
    if "BKA_ALGLOBALS_DEFINED" not in content:
        last_endif_idx = content.rfind('#endif')
        
        if last_endif_idx != -1:
            content = content[:last_endif_idx] + struct_def + "\n" + content[last_endif_idx:]
        else:
            # Fallback if the include guard was malformed
            content += struct_def

        with open(header_path, 'w') as f:
            f.write(content)
        print("✅ Successfully injected concrete ALGlobals definition into n64_types.h")
    else:
        print("✅ ALGlobals definition is already present and properly guarded.")

if __name__ == '__main__':
    patch_alglobals_robustly()
