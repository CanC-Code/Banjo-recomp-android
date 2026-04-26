import os
import re

def harmonize_n64_headers():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Clean environment: Strip any incomplete forward declarations or malformed prior injections
    content = re.sub(r'typedef\s+struct\s+[a-zA-Z0-9_]+\s+ALGlobals\s*;\s*', '', content)
    content = re.sub(r'struct\s+ALGlobals\s*;\s*', '', content)
    content = re.sub(r'/\* Injected OSPri.*?\*/\s*typedef\s+(s32|int)\s+OSPri;\s*', '', content, flags=re.DOTALL)
    content = re.sub(r'typedef\s+(s32|int)\s+OSPri;\s*', '', content)

    # 2. Cumulative Top-Level Injections (M_PI and OSPri)
    # These must be at the absolute top to precede any conditional macro evaluations in the C source files
    top_injections = ""
    
    if "BKA_OSPRI_DEFINED" not in content:
        top_injections += """#ifndef BKA_OSPRI_DEFINED
#define BKA_OSPRI_DEFINED
/* Injected OSPri for libultra compatibility */
typedef int OSPri;
#endif

"""
        
    # We use a unique BKA_ prefix guard to bypass false positives from commented-out code in the header
    if "BKA_MPI_GUARANTEE" not in content:
        top_injections += """#ifndef BKA_MPI_GUARANTEE
#define BKA_MPI_GUARANTEE
/* Expose M_PI in POSIX math.h, and provide a compiler-evaluated fallback */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE 1
#endif
#ifndef _USE_MATH_DEFINES
#define _USE_MATH_DEFINES 1
#endif
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#endif

"""

    if top_injections:
        content = top_injections + content.lstrip()

    # 3. Structural layout for ALGlobals 
    # Safely injected near the end to capture any preceding dependencies
    if "BKA_ALGLOBALS_DEFINED" not in content:
        struct_def = """
#ifndef BKA_ALGLOBALS_DEFINED
#define BKA_ALGLOBALS_DEFINED

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
        last_endif_idx = content.rfind('#endif')
        if last_endif_idx != -1:
            content = content[:last_endif_idx] + struct_def + "\n" + content[last_endif_idx:]
        else:
            content += struct_def

    with open(header_path, 'w') as f:
        f.write(content)
    
    print("✅ Source harmonizer successfully applied cumulative mathematical and structural patches to n64_types.h")

if __name__ == '__main__':
    harmonize_n64_headers()
