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

    # Strip any prior harmonizer injection to prevent stacking
    if "/* --- HARMONIZER_" in content:
        print("[!] Found previous harmonizer injection. Stripping to apply fresh...")
        content = content.split("/* --- HARMONIZER_")[0]

    # =============================================
    # FIX 1: Replace scalar `Acmd` with struct `Acmd`
    # =============================================
    before = len(content)
    content = re.sub(
        r'typedef\s+u64\s+Acmd\s*;',
        'typedef struct { u32 w0; u32 w1; } Acmd;',
        content
    )
    if len(content) < before:
        print("[+] Replaced scalar `Acmd` with struct `Acmd`.")
    else:
        print("[!] WARNING: Scalar `Acmd` not found — may already be a struct.")

    # =============================================
    # FIX 2: Patch ALFilter to use ALCmdHandler/ALSetParam
    # =============================================
    def patch_alfilter(src):
        pattern = (
            r'(typedef\s+struct\s+ALFilter_s\s*\{}'
            r'(.*?)'
            r'(\}\s*ALFilter\s*;)'
        )
        m = re.search(pattern, src, re.DOTALL)
        if not m:
            print("[!] WARNING: struct ALFilter_s not found — skipping patch.")
            return src
        open_tok = m.group(1)
        body = m.group(2)
        close_tok = m.group(3)

        # Replace void *handler with ALCmdHandler
        body = re.sub(r'void\s+\*handler\s*;', 'ALCmdHandler handler;', body)
        # Replace void *setParam with ALSetParam
        body = re.sub(r'void\s+\*setParam\s*;', 'ALSetParam setParam;', body)

        return src[:m.start()] + open_tok + body + close_tok + src[m.end():]

    content = patch_alfilter(content)

    # =============================================
    # FIX 3: Remove `typedef ALPVoice N_PVoice` (conflict)
    # =============================================
    before = len(content)
    content = re.sub(r'[ \t]*typedef\s+ALPVoice\s+N_PVoice\s*;\s*\n', '', content)
    if len(content) < before:
        print("[+] Removed conflicting `typedef ALPVoice N_PVoice` line.")
    else:
        print("[!] WARNING: `typedef ALPVoice N_PVoice` not found — may already be absent.")

    # =============================================
    # FIX 4: Patch ALPVoice_s to add `offset` field
    # =============================================
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
        open_tok = m.group(1)
        body = m.group(2)
        close_tok = m.group(3)
        for decl, field_name in fields_to_add:
            if re.search(rf'\b{re.escape(field_name)}\b', body):
                print(f"    [=] {struct_tag}.{field_name} already present.")
            else:
                print(f"    [+] Injecting {struct_tag}.{field_name}")
                body = body.rstrip() + f"\n    {decl}"
        return src[:m.start()] + open_tok + body + close_tok + src[m.end():]

    content = patch_struct_body(content, 'ALPVoice_s', [
        ('s32                 offset;       /* sample offset into wave */', 'offset'),
    ])

    # =============================================
    # Injection Block: Define ALParam, ALCmdHandler, ALSetParam
    # =============================================
    injection = """/* --- HARMONIZER_V11_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

/*
 * ALParam — full sequencer parameter struct.
 * Required by synthInternals.h and n_synth.h.
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

typedef ALParam ALStartParam;
typedef ALParam ALStartParamAlt;
#endif /* BKA_ALPARAM_DEFINED */

/*
 * ALCmdHandler — required by synthInternals.h:92.
 * ALSetParam   — required by synthInternals.h:92 and n_synth.h:130.
 */
#ifndef BKA_ALHANDLERS_DEFINED
#define BKA_ALHANDLERS_DEFINED
typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*ALSetParam)(void *, s32, void *);
#endif /* BKA_ALHANDLERS_DEFINED */

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

    new_content = content.rstrip() + "\n\n" + injection

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[+] Successfully applied V11 patch. Wrote {len(new_content)} bytes to {filepath}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android"
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()
    run_phase2_harmonizer(args.root)