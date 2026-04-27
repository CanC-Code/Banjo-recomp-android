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
        print("[!] Found previous harmonizer injection. Stripping to apply fresh...")
        content = content.split("/* --- HARMONIZER_")[0]

    # -------------------------------------------------------------------------
    # FIX 1: Remove `typedef ALPVoice N_PVoice` — n_synth.h defines
    # `struct N_PVoice_s { ... } N_PVoice` as a different struct and must
    # own that name. Confirmed by redefinition error across all prior runs.
    # -------------------------------------------------------------------------
    before = len(content)
    content = re.sub(r'[ \t]*typedef\s+ALPVoice\s+N_PVoice\s*;\s*\n', '', content)
    if len(content) < before:
        print("[+] Removed conflicting `typedef ALPVoice N_PVoice` line.")
    else:
        print("[!] WARNING: `typedef ALPVoice N_PVoice` not found — may already be absent.")

    # -------------------------------------------------------------------------
    # FIX 2: Patch ALPVoice_s in-place to add `offset` field.
    # Required by n_synstartvoice.c:38 and n_synstartvoiceparam.c:27.
    # -------------------------------------------------------------------------
    def patch_struct_body(src, struct_tag, fields_to_add):
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

    content = patch_struct_body(content, 'ALPVoice_s', [
        ('s32                 offset;       /* sample offset into wave */', 'offset'),
    ])

    # -------------------------------------------------------------------------
    # Injection block — complete set of what the C audio files need:
    #
    # MUST provide (bare names, no WRAPPER_ prefix):
    #   - ALParam struct    used by synthInternals.h:124,125,207,208
    #                       and n_synth.h:71,72,116,117,155,156
    #   - ALStartParam      used by n_synstartvoice.c:25,29
    #   - ALStartParamAlt   used by n_synstartvoiceparam.c:10,18
    #   - ALCmdHandler      used by synthInternals.h:92
    #
    # MUST NOT provide:
    #   - ALSetParam as a function pointer — synthInternals.h defines it at
    #     line 154 as `typedef s32 (*ALSetParam)(void*, s32, void*)` and
    #     n_synth.h:130 uses it as a field type. We must not shadow it.
    #   - ALSetFXParam      synthInternals.h:154 owns this
    #   - N_PVoice          n_synth.h owns this (removed above)
    #   - WRAPPER_* structs already defined in header body
    #
    # ORDER MATTERS: ALParam struct must appear before ALCmdHandler typedef
    # because synthInternals.h processes top-to-bottom.
    # -------------------------------------------------------------------------
    injection = """/* --- HARMONIZER_V9_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

/*
 * ALParam — full sequencer parameter struct.
 * Required by include/synthInternals.h (lines 124,125,207,208)
 *        and include/n_synth.h         (lines 71,72,116,117,155,156)
 *        and src/core1/audio/n_synstartvoice.c
 *        and src/core1/audio/n_synstartvoiceparam.c
 * Must be defined BEFORE synthInternals.h is included by those C files.
 * ALSetParam (function pointer) is intentionally omitted here —
 * synthInternals.h:154 defines it and n_synth.h:130 uses it.
 */
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

/* Aliases used directly by the C source files */
typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;
#endif /* BKA_ALPARAM_DEFINED */

/* ALCmdHandler — required by synthInternals.h:92
 * Must be a bare name (no WRAPPER_ prefix). */
#ifndef BKA_ALCMDHANDLER_DEFINED
#define BKA_ALCMDHANDLER_DEFINED
typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
#endif /* BKA_ALCMDHANDLER_DEFINED */

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

    new_content = content.rstrip() + "\n\n" + injection

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[+] Successfully applied V9 patch. Wrote {len(new_content)} bytes to {filepath}")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android"
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)