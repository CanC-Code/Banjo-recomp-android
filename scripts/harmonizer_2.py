#!/usr/bin/env python3
import os
import argparse
import subprocess

def apply_macro_harmonization(workspace_root):
    """
    Uses C-preprocessor macros to dynamically rename conflicting types during 
    the compilation of n64_types.h, bypassing the need for fragile regex stripping.
    """
    filepath = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h")
    if not os.path.exists(filepath):
        print(f"[-] Fatal: n64_types.h not found at {filepath}")
        return False

    # Attempt to reset n64_types.h to its clean, unmodified state to prevent double-patching artifacts
    subprocess.run(["git", "checkout", "--", filepath], cwd=workspace_root, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The exact list of conflicting dummy types generating errors in the ninja build log
    override_list = [
        'ALCmdHandler', 'ALSetParam', 'ALParam', 'ALPVoice', 'N_PVoice', 
        'ALStartParam', 'ALStartParamAlt', 'ALFilter', 'N_ALVoice',
        'ALVoiceState', 'ALEvent', 'ALEventListItem'
    ]

    # Phase 1: Mask the conflicting wrapper types
    top_macros = "\n/* --- HARMONIZER MACRO OVERRIDE START --- */\n"
    for macro in override_list:
        top_macros += f"#define {macro} DUMMY_{macro}\n"
    top_macros += "/* --------------------------------------- */\n\n"

    # Phase 2: Unmask and inject the structurally complete N64 SDK types
    bottom_macros = "\n/* --- HARMONIZER MACRO OVERRIDE END --- */\n"
    for macro in override_list:
        bottom_macros += f"#undef {macro}\n"
    
    bottom_macros += """
// Provide the structurally complete ALParam so member offsets can be computed by the core N64 source
typedef struct ALParam_s {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    union { f32 f; s32 i; } data;
} ALParam;

typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;

// Provide correct function pointer signatures
typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*ALSetParam)(void *, s32, void *);

// Forward declare missing sequence markers
typedef struct ALSeqMarker_s ALSeqMarker;
typedef struct ALCSeqMarker_s ALCSeqMarker;

#ifndef ADPCM_STATE_DEF
#define ADPCM_STATE_DEF
typedef struct ADPCM_STATE_s ADPCM_STATE;
#endif
/* --------------------------------------- */
"""

    # Wrap the original content inside our preprocessor directives
    new_content = top_macros + content + bottom_macros

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"[+] Successfully applied C-preprocessor macro masking to: {filepath}")
    return True

def run_phase2_harmonizer(workspace_root):
    print(f"Starting Phase 2 Audio Subsystem Harmonization in: {workspace_root}")

    # 1. Restore native SDK headers to ensure no previous corrupted states
    headers_to_restore = [
        "include/2.0L/PR/n_libaudio.h",
        "include/synthInternals.h",
        "include/n_synth.h"
    ]
    for h in headers_to_restore:
        h_path = os.path.join(workspace_root, h)
        if os.path.exists(h_path):
            subprocess.run(["git", "checkout", "--", h_path], cwd=workspace_root, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            print(f"[+] Restored baseline SDK header: {h}")

    # 2. Execute the macro-level masking to safely bypass wrapper conflicts
    apply_macro_harmonization(workspace_root)
    
    print("Phase 2 source harmonization successfully completed using Preprocessor Masking.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)
