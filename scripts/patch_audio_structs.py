import os
import re

def patch_audio_structs():
    """
    Fixes missing fields in the N_ALSyn structure within n64_types.h
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the N_ALSyn_s (or N_ALSyn) struct and add sv_dramout
    if 'sv_dramout' not in content:
        print("🛠️ Patching N_ALSyn structure for sv_dramout...")
        # Matches the struct N_ALSyn_s { ... } pattern
        pattern = r'(struct\s+N_ALSyn_s\s*\{[^}]*)(\};)'
        # Inject the missing member before the closing brace
        content = re.sub(pattern, r'\1    int sv_dramout;\n\2', content)

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ N_ALSyn structure successfully patched.")

if __name__ == '__main__':
    patch_audio_structs()
