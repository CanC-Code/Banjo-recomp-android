import os
import re

def patch_null_floats(directory):
    print(f"🔍 Scanning {directory} for {{NULL...}} initialization errors...")
    match_count = 0
    
    # Matches {NULL}, {NULL, NULL}, {NULL, NULL, NULL, NULL}, etc.
    pattern = re.compile(r'\{(?:\s*NULL\s*,)*\s*NULL\s*\}')
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.c') or file.endswith('.h'):
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                if pattern.search(content):
                    # Replace with proper C/C++ universal zero initialization
                    new_content = pattern.sub('{0}', content)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    match_count += 1
                    print(f"  🩹 Patched: {filepath}")
                    
    print(f"✅ Finished patching {match_count} files.")

if __name__ == '__main__':
    patch_null_floats('src')
