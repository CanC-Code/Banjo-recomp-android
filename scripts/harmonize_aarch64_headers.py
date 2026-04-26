#!/usr/bin/env python3
import os
import re
import argparse
import sys

def apply_regex_patch(filepath, patches):
    """
    Applies regex substitutions to a file. 
    Handles whitespace variability and multi-line patching robustly.
    """
    if not os.path.exists(filepath):
        print(f"[-] Warning: Target file not found: {filepath}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    for pattern, replacement in patches:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Successfully harmonized: {filepath}")
        return True
    else:
        print(f"[=] No changes required (or patterns already patched) in: {filepath}")
        return False

def ensure_include(filepath, include_stmt):
    """
    Safely injects an include statement at the top of the file if it is missing.
    """
    if not os.path.exists(filepath):
        print(f"[-] Warning: Target file not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if include_stmt not in content:
        content = include_stmt + "\n" + content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[+] Added {include_stmt} to {filepath}")

def run_harmonizer(workspace_root):
    print(f"Starting AArch64 Source Harmonization in: {workspace_root}")

    # 1. Fix LP64 Data Model Mismatches in ultratypes.h
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "ultratypes.h"), [
        (r'typedef\s+unsigned\s+long\s+u32\s*;', 'typedef unsigned int u32;'),
        (r'typedef\s+long\s+s32\s*;', 'typedef signed int s32;')
    ])

    # 2. Fix broken include path in vla.h
    apply_regex_patch(os.path.join(workspace_root, "include", "core2", "vla.h"), [
        (r'#include\s*<ultratypes\.h>', '#include <PR/ultratypes.h>')
    ])

    # 3. Resolve Acmd union vs u64 collision in abi.h
    # Removes the SDK's typedef so n64_types.h can safely assert u64 Acmd
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "abi.h"), [
        (r'\}\s*Acmd\s*;', '} orig_Acmd;'),
        (r'typedef\s+orig_Acmd\s+Acmd\s*;', '/* typedef orig_Acmd Acmd; removed for n64_types.h compatibility */')
    ])

    # 4. Resolve alGlobals pointer type collision in libaudio.h
    # Defers the extern definition strictly to n64_types.h
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "libaudio.h"), [
        (r'extern\s+(struct\s+ALGlobals_s|ALGlobals)\s*\*\s*alGlobals\s*;', '/* alGlobals extern deferred to n64_types.h */')
    ])

    # 5. Fix ALGlobals pointer instantiation in stubs.cpp
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "emulator", "stubs.cpp"), [
        (r'ALGlobals\s*\*\s*alGlobals\s*=\s*nullptr\s*;', 'struct ALGlobals_s* alGlobals = nullptr;')
    ])

    # 6. Fix ALGlobals extern and casting in NativeBridge.cpp
    native_bridge_path = os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "NativeBridge.cpp")
    apply_regex_patch(native_bridge_path, [
        (r'extern\s+ALGlobals\s*\*\s*alGlobals\s*;', 'extern struct ALGlobals_s* alGlobals;'),
        (r'\(\s*ALGlobals\s*\*\s*\)', '(struct ALGlobals_s*)')
    ])
    ensure_include(native_bridge_path, "#include <string.h>")

    # 7. Inject missing standard library references for memcpy
    ensure_include(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "otr_builder.cpp"), "#include <string.h>")

    print("Source harmonization complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harmonize N64 SDK headers for AArch64 Android Recompilation")
    parser.add_argument("--root", type=str, default=".", help="Root directory of the repository")
    args = parser.parse_args()
    
    if not os.path.exists(os.path.join(args.root, "include")):
        print(f"[-] Critical Error: 'include' directory not found in {args.root}")
        sys.exit(1)

    run_harmonizer(args.root)
    sys.exit(0)
