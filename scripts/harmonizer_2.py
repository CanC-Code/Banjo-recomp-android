#!/usr/bin/env python3
import os
import re
import sys
import subprocess

def run_phase2_harmonizer(workspace_root):
    print(f"[+] Starting Phase 2 Audio Subsystem Harmonization in: {workspace_root}")

    # 1. Target the problematic forced-include wrapper file
    filepath = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h")
    
    if not os.path.exists(filepath):
        print(f"[-] CRITICAL ERROR: Could not find n64_types.h at {filepath}")
        sys.exit(1)
        
    # Attempt to reset n64_types.h to its clean, unmodified state to prevent double-patching artifacts
    subprocess.run(["git", "checkout", "--", filepath], cwd=workspace_root, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if "HARMONIZER_V3_APPLIED" in content:
        print("[!] File already harmonized. Skipping to avoid double-patching.")
        return True

    # 2. Safely isolate the wrapper's audio namespace. 
    # Using \b (word boundary) ensures we strictly rename the token regardless of whitespace or bracket formatting,
    # completely avoiding the fragility of trying to delete multi-line C structs.
    types_to_isolate = [
        'ALCmdHandler', 'ALSetParam', 'ALParam', 'ALPVoice', 'N_PVoice', 
        'ALSetFXParam', 'ALStartParam', 'ALStartParamAlt', 'ALFilter', 'N_ALVoice',
        'ALVoiceState', 'ALEvent', 'ALEventListItem'
    ]
    
    print("[+] Isolating conflicting wrapper namespaces...")
    for t in types_to_isolate:
        content = re.sub(rf'\b{t}\b', f'WRAPPER_{t}', content)
        
    # 3. Inject the structurally exact native definitions required by core1/audio.
    # This provides the correct memory offsets (like v->pvoice->offset) for the N64 C files.
    injection = """
/* --- HARMONIZER_V3_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

#include <PR/ultratypes.h>

// Structurally exact native ALParam
typedef struct ALParam_s {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    union { f32 f; s32 i; } data;
} ALParam;

typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;

// Native Function Pointers
typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*ALSetParam)(void *, s32, void *);
typedef s32  (*ALSetFXParam)(void *, s32, void *);

// Forward declarations to satisfy synthInternals.h compilation
typedef struct ALFilter_s ALFilter;
typedef struct ALPVoice_s ALPVoice;
typedef struct N_PVoice_s N_PVoice;
typedef struct N_ALVoice_s N_ALVoice;

#endif
/* ----------------------------- */
"""
    
    new_content = content + injection
    
    # 4. Write back the cleanly separated file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"[+] Successfully applied Namespace Isolation. Wrote {len(new_content)} bytes to {filepath}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)
