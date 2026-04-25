import os
import re

def patch_naudio_and_sdk_types():
    """
    Expands n64_types.h to include missing SDK types and audio internals
    required by synthInternals.h and model.h, and fixes header collisions.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    include_dir = 'Android/app/src/main/cpp/ultra/' # Directory for polyfills
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    # 1. Create a bool.h polyfill to fix the "bool.h not found" error
    bool_h_path = os.path.join(include_dir, "bool.h")
    with open(bool_h_path, "w") as f:
        f.write("#ifndef _BOOL_H_\n#define _BOOL_H_\n#include <stdbool.h>\n#endif\n")
    print("✅ Created bool.h polyfill.")

    with open(header_path, 'r') as f:
        content = f.read()

    # 2. Add missing SDK and Audio types if not present
    # We define these before the struct patches to ensure visibility
    sdk_types = """
// --- SDK and Audio Internal Types ---
typedef s32 ALPan;
typedef struct {
    u32 words[2];
} Acmd;

typedef struct {
    s16     ob[16];     /* pcm samples */
} ADPCM_STATE;

typedef struct {
    u32     start;
    u32     end;
    u32     count;
    ADPCM_STATE *state;
} ALRawLoop;

typedef s32 (*ALDMAproc)(s32 addr, s32 len, void *state);
typedef ALDMAproc (*ALDMANew)(void *state);

typedef struct {
    u32     force_alignment;
} RESAMPLE_STATE, POLEF_STATE;

typedef struct {
    u32     maxVVoices;
    u32     maxPVoices;
    u32     maxUpdates;
    u32     maxEvents;
    void    *heap;
    u32     outputRate;
    void    *fxType;
} ALSynConfig;

#ifndef _VTX_H_
typedef struct {
    short ob[3];
    unsigned short flag;
    short tc[2];
    unsigned char cn[4];
} Vtx_t;

typedef struct {
    short ob[3];
    unsigned short flag;
    short tc[2];
    signed char n[3];
    unsigned char a;
} Vtx_n;

typedef union {
    Vtx_t v;
    Vtx_n n;
    long long int force_structure_alignment;
} Vtx;
#endif
"""

    if "typedef struct { u32 words[2]; } Acmd;" not in content:
        # Insert types at the top of the file, after the basic u8/s32 defines
        content = re.sub(r'(typedef.*s64;)', r'\1\n' + sdk_types, content)

    # 3. Guard OSThread to prevent redefinition in exceptasm.cpp
    if "typedef struct OSThread_s" in content and "#ifndef _OS_THREAD_GUARD" not in content:
        content = re.sub(
            r'(typedef struct OSThread_s\s+\{.*?\s+\} OSThread;)',
            r'#ifndef _OS_THREAD_GUARD\n#define _OS_THREAD_GUARD\n\1\n#endif',
            content, flags=re.DOTALL
        )

    # 4. Re-apply the sequence arrays for ALCSeq/ALCSeqMarker (Maintenance)
    bk_fields = "    u8 lastStatus[16];\n    u8 *curBUPtr[16];\n"
    
    def clean_and_patch(text, struct_name):
        pattern = r'(struct\s+\w*?' + struct_name + r'.*?\{)(.*?)(\}\s*' + struct_name + r'?;)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            header, body, footer = match.groups()
            body = re.sub(r'.*lastStatus.*;\n?', '', body)
            body = re.sub(r'.*curBUPtr.*;\n?', '', body)
            body = re.sub(r'.*curPtr.*;\n?', '', body)
            new_body = body.rstrip() + "\n" + bk_fields
            return text[:match.start()] + header + new_body + footer + text[match.end():]
        return text

    content = clean_and_patch(content, "ALCSeq")
    content = clean_and_patch(content, "ALCSeqMarker")

    with open(header_path, 'w') as f:
        f.write(content)

    print("✅ n64_types.h updated with PR types, audio states, and redefinition guards.")

if __name__ == '__main__':
    patch_naudio_and_sdk_types()
