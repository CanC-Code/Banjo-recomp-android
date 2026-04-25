import os
import re

def sanitize_and_patch_types():
    """
    Sanitizes n64_types.h by removing duplicate typedefs and injecting 
    the correct BK-specific types with robust preprocessor guards.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ Error: {header_path} not found.")
        return

    with open(header_path, 'r') as f:
        lines = f.readlines()

    # Types that are causing 'typedef redefinition' errors
    conflict_types = [
        'Acmd', 'Vtx', 'Vtx_t', 'Vtx_n', 'ALPan', 
        'ADPCM_STATE', 'ALRawLoop', 'RESAMPLE_STATE', 'POLEF_STATE',
        'ALSynConfig', 'ALDMANew', 'ALDMAproc', 'OSThread'
    ]

    # Filter out any existing lines that define these types to prevent collisions
    # This cleans up both original code and previous failed injection attempts.
    clean_lines = []
    skip_mode = False
    for line in lines:
        # Stop skipping if we hit a closing bracket for a struct we were skipping
        if skip_mode and '}' in line and ';' in line:
            skip_mode = False
            continue
        if skip_mode:
            continue
            
        # Identify lines containing typedefs for our conflict list
        if "typedef" in line and any(re.search(rf'\\b{t}\\b', line) for t in conflict_types):
            # If it's a multiline struct/union, enter skip mode
            if '{' in line and '}' not in line:
                skip_mode = True
            continue
        
        # Also remove the OSThread_s struct definition to allow our guarded version
        if "struct OSThread_s" in line:
            if '{' in line and '}' not in line:
                skip_mode = True
            continue

        clean_lines.append(line)

    content = "".join(clean_lines)

    # Standard BK-Specific Types Block with individual guards
    bk_types_block = """
/* --- Banjo-Kazooie Android Recomp Types Block --- */
#ifndef _BK_SDK_TYPES_H_
#define _BK_SDK_TYPES_H_

#ifndef _ACMD_H_
#define _ACMD_H_
typedef struct { u32 words[2]; } Acmd;
#endif

#ifndef _ALPAN_H_
#define _ALPAN_H_
typedef s32 ALPan;
#endif

#ifndef _ALDMA_H_
#define _ALDMA_H_
typedef s32 (*ALDMAproc)(s32, s32, void *);
typedef ALDMAproc (*ALDMANew)(void *state);
#endif

#ifndef _AUDIO_STATES_H_
#define _AUDIO_STATES_H_
typedef struct { s16 ob[16]; } ADPCM_STATE;
typedef struct { u32 start; u32 end; u32 count; ADPCM_STATE *state; } ALRawLoop;
typedef struct { u32 force_alignment; } RESAMPLE_STATE, POLEF_STATE;
#endif

#ifndef _ALSYNCONFIG_H_
#define _ALSYNCONFIG_H_
typedef struct {
    u32 maxVVoices; u32 maxPVoices; u32 maxUpdates; u32 maxEvents;
    void *heap; u32 outputRate; void *fxType;
} ALSynConfig;
#endif

#ifndef _VTX_H_
#define _VTX_H_
typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef struct { short ob[3]; unsigned short flag; short tc[2]; signed char n[3]; unsigned char a; } Vtx_n;
typedef union { Vtx_t v; Vtx_n n; long long int force_alignment; } Vtx;
#endif

#ifndef _OS_THREAD_GUARD
#define _OS_THREAD_GUARD
typedef struct OSThread_s {
    struct OSThread_s *next;
    s32 priority;
    void *stack;
    void *unused;
} OSThread;
#endif

#endif /* _BK_SDK_TYPES_H_ */
"""

    # Inject the block after basic primitive types (u8, s64, etc.)
    match = re.search(r'typedef.*s64;', content)
    if match:
        insertion_point = match.end()
        final_content = content[:insertion_point] + bk_types_block + content[insertion_point:]
    else:
        final_content = bk_types_block + content

    # Re-apply structural fixes for the Sequencer (Maintenance)
    final_content = re.sub(r'(struct\s+ALCSeq\s+\{)(.*?)(\}\s*ALCSeq;)', 
                           r'\\1\n    u8 lastStatus[16];\n    u8 *curBUPtr[16];\n\\3', 
                           final_content, flags=re.DOTALL)

    with open(header_path, 'w') as f:
        f.write(final_content)

    print("✅ n64_types.h sanitized and BK standard types injected.")

if __name__ == '__main__':
    sanitize_and_patch_types()
