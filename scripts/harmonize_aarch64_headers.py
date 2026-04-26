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
        
        if 'extern "C" {' in content and '#ifdef __cplusplus' not in content:
            patched = re.sub(r'(extern\s+"C"\s*\{)', r'#ifdef __cplusplus\n\1\n#endif', content)
            
            last_brace_idx = patched.rfind('}')
            if last_brace_idx != -1:
                patched = patched[:last_brace_idx] + '#ifdef __cplusplus\n}\n#endif' + patched[last_brace_idx+1:]
            
            if patched != content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(patched)
                print(f"[+] Applied C++ linkage guards to: {filepath}")

def fix_string_shadowing(workspace_root):
    """
    Resolves <cstring> standard library compilation failures by renaming the custom 
    N64 string.h to n64_string.h and updating all internal #include directives.
    """
    string_h_path = os.path.join(workspace_root, "include", "string.h")
    n64_string_path = os.path.join(workspace_root, "include", "n64_string.h")
    
    if os.path.exists(string_h_path):
        os.rename(string_h_path, n64_string_path)
        print("[+] Renamed include/string.h to include/n64_string.h to prevent NDK shadowing")
    
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

def fix_time_shadowing(workspace_root):
    """
    Resolves <ctime> standard library compilation failures by renaming 
    the custom SDK time.h to n64_time.h to prevent NDK namespace shadowing.
    """
    time_h_path = os.path.join(workspace_root, "include", "time.h")
    n64_time_path = os.path.join(workspace_root, "include", "n64_time.h")
    
    if os.path.exists(time_h_path):
        os.rename(time_h_path, n64_time_path)
        print("[+] Renamed include/time.h to include/n64_time.h to prevent NDK shadowing")
    
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
                    if filepath == n64_time_path:
                        continue
                    apply_regex_patch(filepath, [
                        (r'^#include\s*[<"]time\.h[>"]', '#include "n64_time.h"')
                    ])

def patch_stdlib_conflicts(workspace_root):
    """
    Comments out standard library redefinitions in the SDK headers 
    that conflict with Android NDK's bionic libc 'overloadable' attributes.
    """
    # Patch newly renamed n64_string.h
    apply_regex_patch(os.path.join(workspace_root, "include", "n64_string.h"), [
        (r'(\bvoid\s+strcat\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */'),
        (r'(\bvoid\s+strcpy\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */'),
        (r'(\bs32\s+strlen\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */')
    ])

    # Patch core1/mem.h
    apply_regex_patch(os.path.join(workspace_root, "include", "core1", "mem.h"), [
        (r'(\bvoid\s+memcpy\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */'),
        (r'(\bvoid\s+memmove\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */')
    ])

    # Patch functions.h
    apply_regex_patch(os.path.join(workspace_root, "include", "functions.h"), [
        (r'(\bvoid\s*\*\s*malloc\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */'),
        (r'(\bvoid\s*\*\s*realloc\s*\([^)]*\)\s*;)', r'/* \1 disabled for NDK */')
    ])

def run_harmonizer(workspace_root):
    print(f"Starting AArch64 Source Harmonization in: {workspace_root}")

    # 1. Fix LP64 Data Model Mismatches
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "ultratypes.h"), [
        (r'typedef\s+unsigned\s+long\s+u32\s*;', 'typedef unsigned int u32;'),
        (r'typedef\s+long\s+s32\s*;', 'typedef signed int s32;')
    ])

    # 2. Fix broken include path
    apply_regex_patch(os.path.join(workspace_root, "include", "core2", "vla.h"), [
        (r'#include\s*<ultratypes\.h>', '#include <PR/ultratypes.h>')
    ])

    # 3. Resolve Acmd union vs u64 collision
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "abi.h"), [
        (r'\}\s*Acmd\s*;', '} orig_Acmd;\ntypedef u64 Acmd;')
    ])

    # 4. Resolve alGlobals pointer type collision
    apply_regex_patch(os.path.join(workspace_root, "include", "2.0L", "PR", "libaudio.h"), [
        (r'extern\s+(struct\s+ALGlobals_s|ALGlobals)\s*\*\s*alGlobals\s*;', '/* alGlobals extern deferred to n64_types.h */')
    ])

    # 5. Fix ALGlobals pointer instantiation
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "emulator", "stubs.cpp"), [
        (r'ALGlobals\s*\*\s*alGlobals\s*=\s*nullptr\s*;', 'struct ALGlobals_s* alGlobals = nullptr;')
    ])

    # 6. Fix ALGlobals extern casting and missing string includes
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "NativeBridge.cpp"), [
        (r'extern\s+ALGlobals\s*\*\s*alGlobals\s*;', 'extern struct ALGlobals_s* alGlobals;'),
        (r'\(\s*ALGlobals\s*\*\s*\)', '(struct ALGlobals_s*)'),
        (r'\bmemset\b', '__builtin_memset')
    ])

    # 7. Replace memcpy with builtin in otr_builder.cpp
    apply_regex_patch(os.path.join(workspace_root, "Android", "app", "src", "main", "cpp", "ultra", "otr_builder.cpp"), [
        (r'\bmemcpy\b', '__builtin_memcpy')
    ])

    # 8. Resolve pure C compilation failures in PR headers
    patch_extern_c_guards(workspace_root)

    # 9. Isolate custom headers from NDK standard library includes
    fix_string_shadowing(workspace_root)
    fix_time_shadowing(workspace_root)

    # 10. Disable conflicting prototype definitions overlapping with NDK headers
    patch_stdlib_conflicts(workspace_root)

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
