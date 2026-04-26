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

    # ALPVoice/ALParam must NOT be renamed — they are the canonical native types
    # used by core1/audio source files. Only rename types that truly belong to
    # the wrapper namespace and will conflict with SDK headers.
    types_to_isolate = [
        'ALCmdHandler', 'ALSetParam', 'ALSetFXParam',
        'ALStartParam', 'ALStartParamAlt',
        'ALVoiceState', 'ALEvent', 'ALEventListItem',
        'ALFilter', 'N_PVoice', 'N_ALVoice',
    ]

    print("[+] Isolating conflicting wrapper namespaces...")
    for t in types_to_isolate:
        content = re.sub(rf'(?<!WRAPPER_)\b{t}\b', f'WRAPPER_{t}', content)

    # Patch ALPVoice_s in-place: ensure it contains the `offset` field.
    # If the existing struct body lacks it, inject it after the opening brace.
    def patch_struct(src, struct_name, required_fields):
        """
        For each (field_decl, marker_comment) in required_fields, inject the
        field into struct_name if not already present.
        """
        # Match the full struct body
        pattern = rf'(typedef\s+struct\s+{re.escape(struct_name)}\s*\{{)([^}}]*?)(\}}\s*{re.escape(struct_name)}\s*;)'
        m = re.search(pattern, src, re.DOTALL)
        if not m:
            print(f"[!] WARNING: Could not locate struct {struct_name} for patching.")
            return src
        open_brace, body, close = m.group(1), m.group(2), m.group(3)
        for field_decl, field_name in required_fields:
            # Check if the field already exists by name
            if re.search(rf'\b{re.escape(field_name)}\b', body):
                print(f"    [=] {struct_name}.{field_name} already present, skipping.")
            else:
                print(f"    [+] Injecting {struct_name}.{field_name}")
                body = body.rstrip() + f"\n    {field_decl}\n"
        return src[:m.start()] + open_brace + body + close + src[m.end():]

    # Patch ALPVoice_s — needs `offset`
    content = patch_struct(content, 'ALPVoice_s', [
        ('s32                 offset;       /* sample offset into wave */', 'offset'),
    ])

    # Patch ALParam_s — needs the full sequencer parameter set
    content = patch_struct(content, 'ALParam_s', [
        ('s32                 samples;',  'samples'),
        ('f32                 pitch;',    'pitch'),
        ('s16                 unity;',    'unity'),
        ('u8                  pan;',      'pan'),
        ('u8                  volume;',   'volume'),
        ('u8                  fxMix;',    'fxMix'),
        ('void               *wave;',     'wave'),
    ])

    # Append a version marker and forward declarations only (no struct redefinitions)
    injection = """
/* --- HARMONIZER_V6_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

/* Forward declarations for synthInternals.h compatibility */
typedef struct ALFilter_s   WRAPPER_ALFilter;
typedef struct N_PVoice_s   WRAPPER_N_PVoice;
typedef struct N_ALVoice_s  WRAPPER_N_ALVoice;

/* Wrapper-namespaced function pointer typedefs */
typedef void (*WRAPPER_ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*WRAPPER_ALSetParam)(void *, s32, void *);
typedef s32  (*WRAPPER_ALSetFXParam)(void *, s32, void *);

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

    new_content = content.rstrip() + "\n\n" + injection.strip() + "\n"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[+] Successfully applied V6 patch. Wrote {len(new_content)} bytes to {filepath}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)