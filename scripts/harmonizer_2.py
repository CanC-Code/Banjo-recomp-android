#!/usr/bin/env python3
import os
import re
import sys


def run_phase2_harmonizer(workspace_root):
    print(f"[+] Starting Phase 2 Audio Subsystem Harmonization in: {workspace_root}")

    filepath = os.path.join(
        workspace_root,
        "Android", "app", "src", "main", "cpp", "ultra", "n64_types.h"
    )

    if not os.path.exists(filepath):
        print(f"[-] CRITICAL ERROR: Could not find n64_types.h at {filepath}")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # -------------------------------------------------------------------------
    # Strip any prior harmonizer injection to prevent stacking across CI runs
    # -------------------------------------------------------------------------
    if "/* --- HARMONIZER_" in content:
        print("[!] Found previous harmonizer injection. Stripping it to apply fresh...")
        content = content.split("/* --- HARMONIZER_")[0]

    # -------------------------------------------------------------------------
    # Patch ALPVoice_s in-place: add `offset` if missing.
    #
    # The header already defines ALPVoice_s at line 115 as:
    #   typedef struct ALPVoice_s {
    #       ALLink node;
    #       struct N_ALVoice_s *vvoice;
    #   } ALPVoice;
    #
    # core1/audio accesses v->pvoice->offset, so we must add it.
    # -------------------------------------------------------------------------
    def patch_struct_body(src, struct_tag, fields_to_add):
        """
        Locate `typedef struct <struct_tag> { ... } <alias>;` and inject any
        missing fields into the body. fields_to_add is a list of
        (field_declaration_string, field_name_for_existence_check).
        Returns the modified source.
        """
        pattern = (
            rf'(typedef\s+struct\s+{re.escape(struct_tag)}\s*\{{)'
            rf'(.*?)'
            rf'(\}}\s*\w+\s*;)'
        )
        m = re.search(pattern, src, re.DOTALL)
        if not m:
            print(f"[!] WARNING: struct {struct_tag} not found — skipping patch.")
            return src

        open_tok  = m.group(1)
        body      = m.group(2)
        close_tok = m.group(3)

        for decl, field_name in fields_to_add:
            if re.search(rf'\b{re.escape(field_name)}\b', body):
                print(f"    [=] {struct_tag}.{field_name} already present.")
            else:
                print(f"    [+] Injecting {struct_tag}.{field_name}")
                body = body.rstrip() + f"\n    {decl}\n"

        return src[:m.start()] + open_tok + body + close_tok + src[m.end():]

    # Patch ALPVoice_s — needs `offset` for n_synstartvoice.c / n_synstartvoiceparam.c
    content = patch_struct_body(content, 'ALPVoice_s', [
        ('s32                 offset;       /* sample offset into wave */', 'offset'),
    ])

    # Patch ALParam_s — needs the full sequencer parameter fields.
    # The header does NOT currently define ALParam_s at all (it comes from
    # PR/libaudio.h via the SDK include). We therefore need to check whether
    # the SDK-provided definition has been pulled in or not.
    # If ALParam_s is absent from the header text we inject a full definition;
    # if it is present we patch missing fields only.
    if 'ALParam_s' not in content:
        print("[+] ALParam_s not found in header — injecting full definition.")
        alparam_block = """
/* Native ALParam_s — full sequencer parameter struct required by core1/audio */
#ifndef BKA_ALPARAM_DEFINED
#define BKA_ALPARAM_DEFINED
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
#endif /* BKA_ALPARAM_DEFINED */
"""
        # Insert just before the closing #endif of the outer include guard
        if '#endif\n' in content:
            insert_at = content.rfind('#endif\n')
            content = content[:insert_at] + alparam_block + content[insert_at:]
        else:
            content = content.rstrip() + "\n" + alparam_block
    else:
        content = patch_struct_body(content, 'ALParam_s', [
            ('s32                 samples;', 'samples'),
            ('f32                 pitch;',   'pitch'),
            ('s16                 unity;',   'unity'),
            ('u8                  pan;',     'pan'),
            ('u8                  volume;',  'volume'),
            ('u8                  fxMix;',   'fxMix'),
            ('void               *wave;',    'wave'),
        ])

    # -------------------------------------------------------------------------
    # Injection block.
    #
    # CRITICAL RULES derived from reading the actual header:
    #   - WRAPPER_ALFilter      already typedef'd at line 166  → DO NOT re-emit
    #   - WRAPPER_N_PVoice      already typedef'd at line 121  → DO NOT re-emit
    #   - WRAPPER_N_ALVoice     already typedef'd at line 147  → DO NOT re-emit
    #
    # Only emit the function pointer typedefs which are genuinely absent.
    # -------------------------------------------------------------------------
    injection = """/* --- HARMONIZER_V7_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

/* Function pointer typedefs required by the audio subsystem.
 * Forward struct declarations (WRAPPER_ALFilter, WRAPPER_N_PVoice,
 * WRAPPER_N_ALVoice) are intentionally omitted — they are already
 * defined earlier in this header by banjo_structural_patch.py. */
typedef void (*WRAPPER_ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*WRAPPER_ALSetParam)(void *, s32, void *);
typedef s32  (*WRAPPER_ALSetFXParam)(void *, s32, void *);

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

    new_content = content.rstrip() + "\n\n" + injection

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[+] Successfully applied V7 patch. Wrote {len(new_content)} bytes to {filepath}")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android"
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)