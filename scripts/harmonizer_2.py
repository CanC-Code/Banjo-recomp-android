#!/usr/bin/env python3
import os
import re
import argparse
import subprocess

def aggressive_replace(filepath):
    """
    Safely and aggressively comments out conflicting type definitions 
    without relying on exact whitespace matching.
    """
    if not os.path.exists(filepath):
        print(f"[-] Target wrapper not found: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Disable single-line aliases robustly
    disables = [
        r'typedef\s+ALEvent\s+N_ALEvent\s*;',
        r'typedef\s+ALEventListItem\s+N_ALEventListItem\s*;',
        r'typedef\s+ALVoiceState\s+N_ALVoiceState\s*;',
        r'typedef\s+ALPVoice\s+PVoice\s*;',
        r'typedef\s+ALPVoice\s+N_PVoice\s*;'
    ]
    for pattern in disables:
        content = re.sub(pattern, '/* [Harmonizer] Disabled alias */', content)

    # Disable full multi-line structs robustly
    content = re.sub(r'typedef\s+struct\s+N_ALVoice_s\s*\{[^}]*\}\s*N_ALVoice\s*;', '/* [Harmonizer] N_ALVoice struct disabled */', content, flags=re.MULTILINE)
    content = re.sub(r'typedef\s+struct\s+ALFilter_s\s*\{[^}]*\}\s*ALFilter\s*;', '/* [Harmonizer] ALFilter struct disabled */', content, flags=re.MULTILINE)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Successfully aggressively harmonized wrapper: {filepath}")
        return True
    
    print("[-] No changes were made to the wrapper. (Already patched?)")
    return False

def prepend_to_file(filepath, text):
    """
    Injects required definitions safely at the top of a file.
    """
    if not os.path.exists(filepath):
        print(f"[-] File not found for injection: {filepath}")
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple check to avoid double-injection
    if "BKA_AUDIO_PATCH_H" not in content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text + content)
        print(f"[+] Injected structural forward declarations into: {filepath}")

def run_phase2_harmonizer(workspace_root):
    print(f"Starting Phase 2 Audio Subsystem Harmonization in: {workspace_root}")

    # 1. Restore native SDK headers to bring back the engine fields (e.g., ALPVoice->offset)
    print("[+] Restoring SDK audio headers to original state...")
    headers_to_restore = [
        "include/2.0L/PR/n_libaudio.h",
        "include/synthInternals.h",
        "include/n_synth.h"
    ]
    for h in headers_to_restore:
        h_path = os.path.join(workspace_root, h)
        if os.path.exists(h_path):
            subprocess.run(["git", "checkout", "--", h_path], cwd=workspace_root)
            print(f"    -> Restored: {h}")

    # 2. Patch the emulator wrapper (n64_types.h)
    n64_types_path = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h")
    aggressive_replace(n64_types_path)

    # 3. Define the missing structural parameters required by n_synstartvoice.c
    # We must provide the actual struct layout so the compiler can resolve member assignments like 'update->delta'
    struct_injection = """
#ifndef BKA_AUDIO_PATCH_H
#define BKA_AUDIO_PATCH_H

typedef struct ALParam_s {
    struct ALParam_s *next;
    s32 delta;
    s16 type;
    union { f32 f; s32 i; } data;
} ALParam;

typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;

typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*ALSetParam)(void *, s32, void *);

typedef struct ALSeqMarker_s ALSeqMarker;
typedef struct ALCSeqMarker_s ALCSeqMarker;

#ifndef ADPCM_STATE_DEF
#define ADPCM_STATE_DEF
typedef struct ADPCM_STATE_s ADPCM_STATE;
#endif

#endif // BKA_AUDIO_PATCH_H

"""

    # Inject these definitions into the internal N64 headers
    synth_internals_path = os.path.join(workspace_root, "include", "synthInternals.h")
    n_synth_path = os.path.join(workspace_root, "include", "n_synth.h")
    n_libaudio_path = os.path.join(workspace_root, "include", "2.0L", "PR", "n_libaudio.h")
    
    prepend_to_file(synth_internals_path, struct_injection)
    prepend_to_file(n_synth_path, struct_injection)
    prepend_to_file(n_libaudio_path, struct_injection)

    print("Phase 2 source harmonization strictly completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)
