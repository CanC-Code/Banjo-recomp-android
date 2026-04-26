#!/usr/bin/env python3
import os
import argparse
import sys

def patch_file(filepath, replacements):
    """
    Reads a file, applies a list of string replacements, and writes it back.
    Prioritizes functional correctness and avoids regression by checking if
    the patch is actually needed.
    """
    if not os.path.exists(filepath):
        print(f"[-] Error: Target file not found: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    for old_str, new_str in replacements:
        if old_str in content:
            content = content.replace(old_str, new_str)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Successfully harmonized: {filepath}")
        return True
    else:
        print(f"[=] No changes required (or patterns already patched) in: {filepath}")
        return False

def run_harmonizer(workspace_root):
    print(f"Starting AArch64 Source Harmonization in: {workspace_root}")

    # 1. Fix LP64 Data Model Mismatches in ultratypes.h
    # The legacy SDK defines u32 as unsigned long (which is 64-bit on arm64-v8a) 
    # and s32 as long. These must map to unsigned int and signed int.
    ultratypes_path = os.path.join(workspace_root, "include", "2.0L", "PR", "ultratypes.h")
    ultratypes_replacements = [
        ("typedef unsigned long                   u32;", "typedef unsigned int                    u32;"),
        ("typedef long                            s32;", "typedef signed int                      s32;")
    ]
    patch_file(ultratypes_path, ultratypes_replacements)

    # 2. Fix broken include path in vla.h
    # vla.h expects ultratypes.h to be in the same directory or standard path, 
    # but the SDK puts it in PR/.
    vla_path = os.path.join(workspace_root, "include", "core2", "vla.h")
    vla_replacements = [
        ("#include<ultratypes.h>", "#include <PR/ultratypes.h>")
    ]
    patch_file(vla_path, vla_replacements)

    # 3. Resolve Acmd union vs u64 collision in abi.h
    # n64_types.h (injected via -include) defines Acmd as u64, which destroys
    # the SDK's struct definition. We rename the SDK's internal union and 
    # guard the typedef.
    abi_path = os.path.join(workspace_root, "include", "2.0L", "PR", "abi.h")
    abi_replacements = [
        ("} Acmd;", "} orig_Acmd;\n\n#ifndef _N64_TYPES_H_\ntypedef orig_Acmd Acmd;\n#endif")
    ]
    patch_file(abi_path, abi_replacements)

    # 4. Resolve alGlobals pointer type mismatch in libaudio.h
    # n64_types.h declares: extern struct ALGlobals_s *alGlobals;
    # libaudio.h declares: extern ALGlobals *alGlobals;
    # We comment out the SDK's version and replace it with the wrapper's expectation.
    libaudio_path = os.path.join(workspace_root, "include", "2.0L", "PR", "libaudio.h")
    libaudio_replacements = [
        ("extern ALGlobals *alGlobals;", "/* Harmonized for AArch64 wrapper */\n/* extern ALGlobals *alGlobals; */\nextern struct ALGlobals_s *alGlobals;")
    ]
    patch_file(libaudio_path, libaudio_replacements)

    print("Source harmonization complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harmonize N64 SDK headers for AArch64 Android Recompilation")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()
    
    # Ensure the script exits with an error code if critical directories are missing
    if not os.path.exists(os.path.join(args.root, "include")):
        print(f"[-] Critical Error: 'include' directory not found in {args.root}")
        sys.exit(1)

    run_harmonizer(args.root)
    sys.exit(0)
