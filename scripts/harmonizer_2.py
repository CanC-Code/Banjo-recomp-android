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
    # FIX 1: Move fundamental types to the TOP of the file
    # =============================================
    fundamental_types = """
/* =========================
   FUNDAMENTAL TYPES
   ========================= */
typedef unsigned char      u8;
typedef signed char        s8;
typedef unsigned short     u16;
typedef signed short       s16;
typedef unsigned int       u32;
typedef signed int         s32;
typedef unsigned long long u64;
typedef signed long long   s64;
typedef float              f32;
typedef double             f64;

"""

    # =============================================
    # FIX 2: Add Acmd struct override and neutralize PR/abi.h
    # =============================================
    acmd_override = """
/* =========================
   ACMD OVERRIDE (for PR/abi.h compatibility)
   ========================= */
#ifndef BKA_ACMD_OVERRIDE
#define BKA_ACMD_OVERRIDE
/* Neutralize PR/abi.h's Acmd typedef to avoid conflict */
#define Acmd BKA_Acmd_Neutralized
typedef struct { u32 w0; u32 w1; } Acmd;
#undef Acmd

/* Redefine aClearBuffer to work with Acmd as a struct */
#undef aClearBuffer
#define aClearBuffer(_a, _d, _c) \\
    (_a)->w0 = _SHIFTL(A_CLEARBUFF, 24, 8) | _SHIFTL((_d), 0, 24), \\
    (_a)->w1 = (unsigned int)(_c)
#endif

"""

    # =============================================
    # Rebuild the file with the correct order:
    # 1. Header guard
    # 2. Fundamental types
    # 3. Acmd override and macro redefinition
    # 4. Rest of the file
    # =============================================
    header_guard_pattern = r'(#ifndef BKA_ANDROID_N64_TYPES_H\s*\n#define BKA_ANDROID_N64_TYPES_H\s*\n)'
    if re.search(header_guard_pattern, content):
        header_guard = re.search(header_guard_pattern, content).group(0)
        content = content.replace(header_guard, "")
        new_content = header_guard + fundamental_types + acmd_override + content
        print("[+] Reordered file: header guard -> fundamental types -> Acmd override -> rest.")
    else:
        print("[!] WARNING: Could not find header guard — prepending all fixes.")
        new_content = fundamental_types + acmd_override + content

    content = new_content

    # =============================================
    # FIX 3: Patch ALFilter to use ALCmdHandler/ALSetParam
    # =============================================
    def patch_alfilter(src):
        pattern = (
            r'(typedef\s+struct\s+ALFilter_s\s*\{)'
            r'([^}]*?)'
            r'(\}\s*ALFilter\s*;)'
        )
        m = re.search(pattern, src, re.DOTALL)
        if not m:
            print("[!] WARNING: struct ALFilter_s not found — skipping patch.")
            return src
        open_tok = m.group(1)
        body = m.group(2)
        close_tok = m.group(3)

        # Patch handler and setParam to use the correct types
        body = re.sub(r'void\s+\*handler\s*;', 'Acmd *(*handler)(void *, s16 *, s32, s32, void *);', body)
        body = re.sub(r'void\s+\*setParam\s*;', 'ALSetParam setParam;', body)

        return src[:m.start()] + open_tok + body + close_tok + src[m.end():]

    content = patch_alfilter(content)

    # =============================================
    # FIX 4: Remove `typedef ALPVoice N_PVoice` (conflict)
    # =============================================
    before = len(content)
    content = re.sub(r'[ \t]*typedef\s+ALPVoice\s+N_PVoice\s*;\s*\n', '', content)
    if len(content) < before:
        print("[+] Removed conflicting `typedef ALPVoice N_PVoice` line.")
    else:
        print("[!] WARNING: `typedef ALPVoice N_PVoice` not found — may already be absent.")

    # =============================================
    # FIX 5: Patch ALPVoice_s to add `offset` field
    # =============================================
    def patch_struct_body(src, struct_tag, fields_to_add):
        pattern = (
            rf'(typedef\s+struct\s+{re.escape(struct_tag)}\s*\{{)'
            r'([^}]*?)'
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
    # Place this RIGHT AFTER the includes and BEFORE any structs
    # =============================================
    # Find the end of the includes section (after #include "PR/libaudio.h")
    include_end_pattern = r'(#include\s+"PR/libaudio\.h"\s*\n)'
    m = re.search(include_end_pattern, content)
    if m:
        include_end_pos = m.end()
        injection = """

/* --- HARMONIZER_V16_APPLIED --- */
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
 * Updated to return Acmd* and take 5 arguments to match auxbus.c usage.
 * ALSetParam   — required by synthInternals.h:92 and n_synth.h:130.
 */
#ifndef BKA_ALHANDLERS_DEFINED
#define BKA_ALHANDLERS_DEFINED
typedef Acmd *(*ALCmdHandler)(void *, s16 *, s32, s32, void *);  // Returns Acmd* and takes 5 args
typedef s32  (*ALSetParam)(void *, s32, void *);
#endif /* BKA_ALHANDLERS_DEFINED */

#endif /* BKA_HARMONIZER_INJECT */
/* ----------------------------- */
"""

        content = content[:include_end_pos] + injection + content[include_end_pos:]
        print("[+] Injected harmonizer types after includes.")
    else:
        print("[!] WARNING: Could not find #include \"PR/libaudio.h\" — injecting at top of file.")
        content = injection + "\n" + content

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[+] Successfully applied V16 patch. Wrote {len(content)} bytes to {filepath}")
    return True

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Phase 2: Harmonize Audio Subsystem SDK for AArch64 Android"
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()
    run_phase2_harmonizer(args.root)