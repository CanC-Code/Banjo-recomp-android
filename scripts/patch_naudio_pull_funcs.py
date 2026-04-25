import os
import re

def sanitize_and_patch_types():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path):
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. List of types to completely remove before re-adding
    types_to_clean = [
        'ALPan', 'Acmd', 'ADPCM_STATE', 'ALRawLoop', 
        'RESAMPLE_STATE', 'POLEF_STATE', 'ALSynConfig', 
        'Vtx_t', 'Vtx_n', 'Vtx', 'ALDMANew', 'ALDMAproc'
    ]

    # 2. Aggressively strip existing definitions (handles multi-line structs/unions)
    for t in types_to_clean:
        # Pattern for "typedef struct/union { ... } TypeName;"
        content = re.sub(rf'typedef\s+(struct|union)\s+{{.*?}}\s*{t}\s*;', '', content, flags=re.DOTALL)
        # Pattern for "typedef [other] TypeName;"
        content = re.sub(rf'typedef\s+[^;]+?\s*{t}\s*;', '', content)

    # 3. Inject the clean BK-Standard block with individual guards
    bk_types_block = """
#ifndef _BK_SDK_TYPES_H_
#define _BK_SDK_TYPES_H_

typedef s32 ALPan;
typedef struct { u32 words[2]; } Acmd;
typedef struct { s16 ob[16]; } ADPCM_STATE;
typedef struct { u32 start; u32 end; u32 count; ADPCM_STATE *state; } ALRawLoop;
typedef struct { u32 force_alignment; } RESAMPLE_STATE, POLEF_STATE;

typedef struct {
    u32 maxVVoices; u32 maxPVoices; u32 maxUpdates; u32 maxEvents;
    void *heap; u32 outputRate; void *fxType;
} ALSynConfig;

typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef struct { short ob[3]; unsigned short flag; short tc[2]; signed char n[3]; unsigned char a; } Vtx_n;
typedef union { Vtx_t v; Vtx_n n; long long int force_alignment; } Vtx;

typedef s32 (*ALDMAproc)(s32, s32, void *);
typedef ALDMAproc (*ALDMANew)(void *state);

#ifndef _OS_THREAD_GUARD
#define _OS_THREAD_GUARD
typedef struct OSThread_s {
    struct OSThread_s *next;
    s32 priority;
    void *stack;
    void *unused;
} OSThread;
#endif

#endif
"""
    # Insert after primitive types
    match = re.search(r'typedef.*s64;', content)
    if match:
        content = content[:match.end()] + bk_types_block + content[match.end():]
    else:
        content = bk_types_block + content

    with open(header_path, 'w') as f:
        f.write(content)
    print("✅ n64_types.h sanitized and BK types re-injected.")

if __name__ == '__main__':
    sanitize_and_patch_types()
