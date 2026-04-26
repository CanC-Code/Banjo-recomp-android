#!/usr/bin/env python3
import os
import re
import argparse
import subprocess

def fix_n64_types(workspace_root):
    """
    Safely and aggressively strips conflicting mock definitions from the android wrapper
    and injects the correct structural layouts.
    """
    filepath = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h")
    if not os.path.exists(filepath):
        print(f"[-] Fatal: n64_types.h not found at {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 1. Strip all conflicting dummy types from the wrapper
    structs_to_remove = [
        'ALPVoice', 'ALFilter', 'N_ALVoice', 'N_PVoice', 
        'ALParam', 'ALStartParam', 'ALStartParamAlt', 
        'ALCmdHandler', 'ALSetParam'
    ]
    
    for sname in structs_to_remove:
        # Match: typedef struct Name_s { ... } Name;
        content = re.sub(r'(?s)typedef\s+struct\s+' + sname + r'_s\s*\{.*?\}\s*' + sname + r'\s*;', f'/* Stripped dummy {sname}_s */', content)
        # Match: typedef struct { ... } Name;
        content = re.sub(r'(?s)typedef\s+struct\s*\{.*?\}\s*' + sname + r'\s*;', f'/* Stripped dummy anon {sname} */', content)
        # Match: struct Name_s { ... };
        content = re.sub(r'(?s)struct\s+' + sname + r'_s\s*\{.*?\}\s*;', f'/* Stripped struct {sname}_s */', content)
        # Match: typedef X Name;
        content = re.sub(r'typedef\s+[^;\{]+?\s+' + sname + r'\s*;', f'/* Stripped alias {sname} */', content)
        # Match: typedef void (*Name)(...);
        content = re.sub(r'typedef\s+[^;]+?\(\s*\*\s*' + sname + r'\s*\)\s*\([^;]*\)\s*;', f'/* Stripped func ptr {sname} */', content)

    # 2. Inject the correct types at the end of the file.
    # Because n64_types.h is included globally via compiler flags, this guarantees visibility.
    injection = """
/* --- HARMONIZER AUDIO PATCH --- */
#ifndef HARMONIZER_AUDIO_PATCH_H
#define HARMONIZER_AUDIO_PATCH_H

// Provide the structurally complete ALParam so member offsets can be computed
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

#endif // HARMONIZER_AUDIO_PATCH_H
"""
    
    if "HARMONIZER_AUDIO_PATCH_H" not in content:
        content = content + "\n" + injection

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Successfully patched and harmonized: {filepath}")
        return True
    else:
        print("[-] No changes were necessary for n64_types.h")
        return False

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
            subprocess.run(["git", "checkout", "--", h_path], cwd=workspace_root)
            print(f"[+] Restored: {h}")

    # 2. Execute the robust block replacement and global type injection
    if not fix_n64_types(workspace_root):
        print("[!] Warning: Script executed but no regex matches were applied. Verify file paths.")
    
    print("Phase 2 source harmonization successfully completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)
