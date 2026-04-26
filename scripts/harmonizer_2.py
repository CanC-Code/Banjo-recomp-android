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
    # FIX 1: n64_types.h:122 defines `typedef ALPVoice N_PVoice` but
    # n_synth.h defines `struct N_PVoice_s { ... } N_PVoice` — these are
    # different types and cause a redefinition error.
    #
    # The existing line reads:
    #   typedef ALPVoice WRAPPER_N_PVoice;   (line 121)
    #   typedef ALPVoice N_PVoice;           (line 122)
    #
    # We must remove the `typedef ALPVoice N_PVoice;` line entirely so that
    # n_synth.h owns the canonical N_PVoice definition.
    # We keep WRAPPER_N_PVoice since it is used elsewhere in the header.
    # -------------------------------------------------------------------------
    before = len(content)
    content = re.sub(r'[ \t]*typedef\s+ALPVoice\s+N_PVoice\s*;\s*\n', '', content)
    if len(content) < before:
        print("[+] Removed conflicting `typedef ALPVoice N_PVoice` line.")
    else:
        print("[!] WARNING: `typedef ALPVoice N_PVoice` line not found — may already be absent.")

    # -------------------------------------------------------------------------
    # FIX 2: synthInternals.h uses bare `ALCmdHandler` and `ALSetParam` names.
    # Our injection must provide these as bare names, not WRAPPER_ prefixed.
    # We also need `ALSetParam` specifically — note synthInternals.h already
    # defines `ALSetFXParam` itself (confirmed by the note in the error), so
    # we must NOT redefine that.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # FIX 3: Patch ALPVoice_s in-place to add `offset` field needed by
    # n_synstartvoice.c and n_synstartvoiceparam.c.
    # The current struct body only has {ALLink node; struct N_ALVoice_s *vvoice;}
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
    # Injection block.
    #
    # Emit ONLY what is genuinely absent and needed:
    #   - ALCmdHandler    (bare name — required by synthInternals.h:92)
    #   - ALSetParam      (bare name — required by synthInternals.h:92 and n_synth.h:130)
    #
    # Do NOT emit:
    #   - ALSetFXParam    (synthInternals.h already defines it at line 154)
    #   - WRAPPER_ALFilter / WRAPPER_N_PVoice / WRAPPER_N_ALVoice
    #                     (already defined in the header body)
    #   - N_PVoice        (owned by n_synth.h — we removed it above)
    # -------------------------------------------------------------------------
    injection = """/* --- HARMONIZER_V8_APPLIED --- */
#ifndef BKA_HARMONIZER_INJECT
#define BKA_HARMONIZER_INJECT

/* These bare-name typedefs are required by include/synthInternals.h and
 * include/n_synth.h which use the undecorated names and cannot be modified.
 * ALSetFXParam is intentionally omitted — synthInternals.h defines it itself. */
typedef void (*ALCmdHandler)(void *, s16 *, s32, s32 *);
typedef s32  (*ALSetParam)(void *, s32, void *);

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

    new_content = content.rstrip() + "\n\n" + injection

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[+] Successfully applied V8 patch. Wrote {len(new_content)} bytes to {filepath}")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android"
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()

    run_phase2_harmonizer(args.root)