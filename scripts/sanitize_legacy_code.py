import os
import re
import sys

TARGET_DIRS = ["src", "include"]

# 1. EXPANDED FILE RENAMING MAPPING
# Aggressively rename ALL legacy standard library headers to prevent 
# any C++ system hijacks (like <ctime> finding the game's time.h).
FILE_RENAMES = {
    "bool.h": "n64_bool.h",
    "string.h": "n64_string.h",
    "time.h": "n64_time.h",
    "math.h": "n64_math.h",
    "stdlib.h": "n64_stdlib.h",
    "stddef.h": "n64_stddef.h",
    "stdarg.h": "n64_stdarg.h",
    "stdio.h": "n64_stdio.h"
}

# 2. TOKEN REPLACEMENT MAPPING
TOKEN_REPLACEMENTS = {
    r"\bbool\b": "n64_bool",
    r"\btrue\b": "n64_true",
    r"\bfalse\b": "n64_false",
    r"\bTRUE\b": "N64_TRUE",
    r"\bFALSE\b": "N64_FALSE",
}

def sanitize_codebase(root_path):
    print("🧹 Starting Legacy Code Sanitization...")

    # Phase 1: Rename Files
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

    # Phase 2: Patch Includes and Tokens
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
                except Exception:
                    continue
                
                original_content = content

                for old_file, new_file in FILE_RENAMES.items():
                    pattern = rf'#include\s+["<]{old_file}[">]'
                    replacement = f'#include "{new_file}"'
                    content = re.sub(pattern, replacement, content)
                
                for pattern, replacement in TOKEN_REPLACEMENTS.items():
                    content = re.sub(pattern, replacement, content)
                
                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1

    print(f"✅ Sanitization Complete! Patched {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_codebase(root_dir)
