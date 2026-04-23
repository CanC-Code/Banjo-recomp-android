import os
import re

def patch_null_floats(directory):
    print(f"🔍 Scanning {directory} for {{NULL, NULL}} float initialization errors...")
    match_count = 0
    
    # Regex to match {NULL, NULL} or { NULL, NULL } with any spacing
    pattern = re.compile(r'\{\s*NULL\s*,\s*NULL\s*\}')
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.c') or file.endswith('.h'):
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                if pattern.search(content):
                    # Replace with proper C/C++ zero initialization for float structs
                    new_content = pattern.sub('{0, 0.0f}', content)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    match_count += 1
                    print(f"  🩹 Patched: {filepath}")
                    
    print(f"✅ Finished patching {match_count} files.")

if __name__ == '__main__':
    # Run the scanner against the main source code directory
    patch_null_floats('src')
