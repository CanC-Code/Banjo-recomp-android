#!/usr/bin/env python3
import os
import re
import argparse
import subprocess

def apply_regex_patch(filepath, patches):
    """
    Applies regex substitutions to a file safely.
    Handles whitespace variability and multi-line patching robustly.
    """
    if not os.path.exists(filepath):
        print(f"[-] Target file not found for patching: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    for pattern, replacement in patches:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Successfully harmonized wrapper: {filepath}")
        return True
    return False

def prepend_to_file(filepath, text):
    """
    Safely injects unresolvable forward declarations at the top of a file.
    """
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if text.strip() not in content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text + content)
        print(f"[+] Injected forward declarations into: {filepath}")

def run_phase2_harmonizer(workspace_root):
    print(f"Starting Phase 2 Audio Subsystem Harmonization in: {workspace_root}")

    # 1. Revert the destructive struct deferrals from Phase 1
    # We must restore the native SDK bodies so internal engine fields like 'offset' are available.
    print("[+] Reverting SDK audio headers to restore native engine struct bodies...")
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

    # 2. Patch the emulator wrapper (n64_types.h) to eliminate type hijacking
    # This forces the Banjo-Kazooie native C compilation units to use the real SDK structs
    n64_types_path = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h")
    
    wrapper_patches = [
        # Disable multi-line mock structures
        (r'(typedef\s+struct\s+N_ALVoice_s\s*\{[\s\S]*?\}\s*N_ALVoice\s*;)', r'/* \1 disabled for native audio engine */'),
        (r'(typedef\s+struct\s+ALFilter_s\s*\{[\s\S]*?\}\s*ALFilter\s*;)', r'/* \1 disabled for native audio engine */'),
        
        # Disable single-line mock aliases
        (r'(typedef\s+ALEvent\s+N_ALEvent\s*;)', r'/* \1 disabled */'),
        (r'(typedef\s+ALEventListItem\s+N_ALEventListItem\s*;)', r'/* \1 disabled */'),
        (r'(typedef\s+ALVoiceState\s+N_ALVoiceState\s*;)', r'/* \1 disabled */'),
        (r'(typedef\s+ALPVoice\s+PVoice\s*;)', r'/* \1 disabled */'),
        (r'(typedef\s+ALPVoice\s+N_PVoice\s*;)', r'/* \1 disabled */')
    ]
    apply_regex_patch(n64_types_path, wrapper_patches)

    # 3. Safely re-inject the strictly missing opaque pointers into the SDK headers
    # These were legitimately missing from the original N64 headers and cause AArch64 strictness failures
    n_libaudio_path = os.path.join(workspace_root, "include", "2.0L", "PR", "n_libaudio.h")
    prepend_to_file(n_libaudio_path, "typedef struct ALSeqMarker_s ALSeqMarker;\ntypedef struct ALCSeqMarker_s ALCSeqMarker;\n\n")

    synth_internals_path = os.path.join(workspace_root, "include", "synthInternals.h")
    prepend_to_file(synth_internals_path, "#ifndef ADPCM_STATE_DEF\n#define ADPCM_STATE_DEF\ntypedef struct ADPCM_STATE_s ADPCM_STATE;\n#endif\n\n")

    n_synth_path = os.path.join(workspace_root, "include", "n_synth.h")
    prepend_to_file(n_synth_path, "#ifndef ADPCM_STATE_DEF\n#define ADPCM_STATE_DEF\ntypedef struct ADPCM_STATE_s ADPCM_STATE;\n#endif\n\n")

    print("Phase 2 source harmonization complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)
