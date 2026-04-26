#!/usr/bin/env python3
import os
import re
import argparse
import sys

def apply_regex_patch(filepath, patches):
    """
    Applies regex substitutions to a file safely.
    Handles whitespace variability and multi-line patching robustly.
    """
    if not os.path.exists(filepath):
        # Suppress missing file warnings unless debug is needed, keeps log clean
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
        return False

def patch_extern_c_guards(workspace_root):
    """
    Injects #ifdef __cplusplus guards around raw extern "C" blocks in N64 headers
    so that the clang C compiler does not throw identifier errors.
    """
    pr_dir = os.path.join(workspace_root, "include", "2.0L", "PR")
    if not os.path.exists(pr_dir):
        return

    for filename in os.listdir(pr_dir):
        if not filename.endswith(".h"):
            continue
            
        filepath = os.path.join(pr_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Only inject if the block exists and isn't already guarded
        if 'extern "C" {' in content and '#ifdef __cplusplus' not in content:
            # Wrap the opening statement
            patched = re.sub(r'(extern\s+"C"\s*\{)', r'#ifdef __cplusplus\n\1\n#endif', content)
            
            # The closing brace for extern "C" in PR headers is almost always the final brace in the file.
            # Rfind maps the final instance safely without breaking intermediate structs.
            last_brace_idx = patched.rfind('}')
            if last_brace_idx != -1:
                patched = patched[:last_brace_idx] + '#ifdef __cplusplus\n}\n#endif' + patched[last_brace_idx+1:]
            
            if patched != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(patched)
                print(f"[+] Applied C++ linkage guards to: {filepath}")

def fix_string_shadowing(workspace_root):
    """
    Resolves the <cstring> standard library compilation failure by renaming the custom 
    N64 string.h to n64_string.h and updating all internal #include directives.
    """
    string_h_path = os.path.join(workspace_root, "include", "string.h")
    n64_string_path = os.path.join(workspace_root, "include", "n64_string.h")
    
    if os.path.exists(string_h_path):
        os.rename(string_h_path, n64_string_path)
        print("[+] Renamed include/string.h to include/n64_string.h to prevent NDK shadowing")
    
    # Update local includes across the codebase to utilize the newly isolated header name
    search_dirs = [
        os.path.join(workspace_root, "src"),
        os.path.join(workspace_root, "include")
    ]
    
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for root, _, files in os.walk(sdir):
            for file in files:
                if file.endswith((".c", ".cpp", ".h")):
                    filepath = os.path.join(root, file)
                    if filepath == n64_string_path:
                        continue
                    apply_regex_patch(filepath, [
                        (r'^#include\s*[<"]string\.h[>"]', '#include "n64_string.h"')
                    ])

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
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "abi.h"), [
        (r'\}\s*Acmd\s*;', '} orig_Acmd;\ntypedef u64 Acmd;')
    ])

    # 4. Resolve alGlobals pointer type collision in libaudio.h
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "libaudio.h"), [
        (r'extern\s+(struct\s+ALGlobals_s|ALGlobals)\s*\*\s*alGlobals\s*;', '/* alGlobals extern deferred to n64_types.h */')
    ])

    # 5. Fix ALGlobals pointer instantiation in stubs.cpp
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "emulator", "stubs.cpp"), [
        (r'ALGlobals\s*\*\s*alGlobals\s*=\s*nullptr\s*;', 'struct ALGlobals_s* alGlobals = nullptr;')
    ])

    # 6. Fix ALGlobals extern casting and missing string includes in NativeBridge.cpp
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "NativeBridge.cpp"), [
        (r'extern\s+ALGlobals\s*\*\s*alGlobals\s*;', 'extern struct ALGlobals_s* alGlobals;'),
        (r'\(\s*ALGlobals\s*\*\s*\)', '(struct ALGlobals_s*)'),
        (r'\bmemset\b', '__builtin_memset')
    ])

    # 7. Replace memcpy with builtin in otr_builder.cpp to bypass standard library include drops
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "otr_builder.cpp"), [
        (r'\bmemcpy\b', '__builtin_memcpy')
    ])

    # 8. Resolve pure C compilation failures in PR headers
    patch_extern_c_guards(workspace_root)

    # 9. Isolate custom headers from NDK standard library includes
    fix_string_shadowing(workspace_root)

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
