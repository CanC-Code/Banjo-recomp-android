#!/usr/bin/env python3
import os
import re
import sys

def run_phase2_harmonizer(workspace_root):
    print(f"[+] Starting Phase 2 Audio Subsystem Harmonization in: {workspace_root}")

    filepath = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h")

    if not os.path.exists(filepath):
        print(f"[-] CRITICAL ERROR: Could not find n64_types.h at {filepath}")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Strip any prior harmonizer injections to prevent stacking
    if "/* --- HARMONIZER_" in content:
        print("[!] Found previous harmonizer injection. Stripping it to apply fresh...")
        content = content.split("/* --- HARMONIZER_")[0]

    types_to_isolate = [
        'ALCmdHandler', 'ALSetParam', 'ALParam', 'ALPVoice', 'N_PVoice',
        'ALSetFXParam', 'ALStartParam', 'ALStartParamAlt', 'ALFilter', 'N_ALVoice',
        'ALVoiceState', 'ALEvent', 'ALEventListItem'
    ]

    print("[+] Isolating conflicting wrapper namespaces...")
    for t in types_to_isolate:
        content = re.sub(rf'(?<!WRAPPER_)\b{t}\b', f'WRAPPER_{t}', content)

    injection = """
/* --- HARMONIZER_V5_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

#include <PR/ultratypes.h>

// Forward declarations
typedef struct ALFilter_s   ALFilter;
typedef struct ALPVoice_s   ALPVoice;
typedef struct N_PVoice_s   N_PVoice;
typedef struct N_ALVoice_s  N_ALVoice;

// Full ALPVoice_s — offset member required by n_synstartvoice.c / n_synstartvoiceparam.c
typedef struct ALPVoice_s {
    struct ALFilter_s  *clientFilter;
    void               *clientData;
    s32                 offset;       /* sample offset into wave */
    u8                  unityPitch;
    u8                  state;
    u16                 flags;
} ALPVoice;

// Full ALParam_s — all fields required by n_synstartvoice.c / n_synstartvoiceparam.c
typedef struct ALParam_s {
    struct ALParam_s   *next;
    s32                 delta;
    s16                 type;
    s32                 samples;
    f32                 pitch;
    s16                 unity;
    u8                  pan;
    u8                  volume;
    u8                  fxMix;
    void               *wave;
    union { f32 f; s32 i; } data;
} ALParam;

typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;

// Native function pointer typedefs
typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*ALSetParam)(void *, s32, void *);
typedef s32  (*ALSetFXParam)(void *, s32, void *);

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

    new_content = content.rstrip() + "\n\n" + injection.strip() + "\n"

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