import os
import re

def patch_null_floats(directory):
    """
    Scans for {NULL, ...} initialization blocks and replaces them with 0-initializers.
    Updated to handle multi-line blocks and remain safe within the BKA pipeline.
    """
    print(f"🩹 Scanning {directory} for float/pointer initialization errors...")
    
    # Updated pattern: 
    # 1. Handles multi-line via re.DOTALL
    # 2. Matches {NULL}, {NULL, NULL}, etc., regardless of whitespace/newlines
    pattern = re.compile(r'\{(?:\s*NULL\s*,?)+\}', re.DOTALL)
    
    match_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.c', '.h')):
                filepath = os.path.join(root, file)
                
                # Skip the 'ultra' directory to protect our harmonized headers
                if 'ultra' in filepath:
                    continue

                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                if pattern.search(content):
                    # We use {0} as it is the standard C initializer for all types (float, int, ptr)
                    new_content = pattern.sub('{0}', content)
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    match_count += 1
                    print(f"  ✅ Patched NULL-init: {filepath}")

    print(f"✅ Finished patching {match_count} files.")

if __name__ == '__main__':
    # Targeting the source directory
    patch_null_floats('src')
