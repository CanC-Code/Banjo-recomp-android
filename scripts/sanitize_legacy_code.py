import os
import re
import sys

# We only want to patch the legacy game code, NOT our Android wrappers.
TARGET_DIRS = ["src", "include"]

# 1. FILE RENAMING MAPPING
# Keys are original file names, Values are the safe new names.
FILE_RENAMES = {
    "bool.h": "n64_bool.h",
    "string.h": "n64_string.h" # Fixes the system hijack loop permanently
}

# 2. TOKEN REPLACEMENT MAPPING
# Uses regex word boundaries (\b) to ensure we don't accidentally rename 
# a variable named "boolean" to "n64_boolean".
TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "n64_true",
    r"\bfalse\b": "n64_false",
    r"\bTRUE\b": "N64_TRUE",
    r"\bFALSE\b": "N64_FALSE",
    # Add any future C++ keyword clashes here (e.g., r"\bclass\b": "n64_class")
}

def sanitize_codebase(root_path):
    print("🧹 Starting Legacy Code Sanitization...")

    # Phase 1: Rename Problematic Files
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path):
            continue
            
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if filename in FILE_RENAMES:
                    old_file = os.path.join(root, filename)
                    new_file = os.path.join(root, FILE_RENAMES[filename])
                    os.rename(old_file, new_file)
                    print(f"  [Renamed] {old_file} -> {new_file}")

    # Phase 2: Patch Includes and Tokens in all Source Files
    patch_count = 0
    for dir_name in TARGET_DIRS:
        dir_path = os.path.join(root_path, dir_name)
        if not os.path.exists(dir_path):
            continue
            
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not (filename.endswith('.c') or filename.endswith('.h')):
                    continue
                
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception as e:
                    print(f"  [Error] Reading {filepath}: {e}")
                    continue
                
                original_content = content

                # 2A. Update #include directives to match renamed files
                for old_file, new_file in FILE_RENAMES.items():
                    # Matches #include "bool.h" or #include <bool.h>
                    pattern = rf'#include\s+["<]{old_file}[">]'
                    replacement = f'#include "{new_file}"'
                    content = re.sub(pattern, replacement, content)
                
                # 2B. Apply token swaps
                for pattern, replacement in TOKEN_REPLACEMENTS.items():
                    content = re.sub(pattern, replacement, content)
                
                # Write back if changes were made
                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1

    print(f"✅ Sanitization Complete! Patched {patch_count} files.")

if __name__ == "__main__":
    # Allows running directly in the root or passing a path
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
