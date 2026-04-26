import os
import re

def patch_audio_structs():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'sv_dramout' in content:
        print("⏭️ sv_dramout already patched.")
        return

    print("🛠️ Searching for N_ALSyn structure...")
    
    # This matches 'struct N_ALSyn_s {' or 'struct N_ALSyn {' or even anonymous structs labeled N_ALSyn
    # It then finds the closing brace and injects the member.
    struct_match = re.search(r'struct\s+(?:N_ALSyn_s|N_ALSyn)\s*\{', content)
    
    if struct_match:
        # Find the end of this block by matching the next closing brace
        start_idx = struct_match.end()
        end_brace_idx = content.find('}', start_idx)
        
        if end_brace_idx != -1:
            content = (
                content[:end_brace_idx] + 
                "    int sv_dramout; /* Manual injection for n_save.c compatibility */\n" + 
                content[end_brace_idx:]
            )
            with open(header_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ Injected sv_dramout into N_ALSyn structure.")
        else:
            print("❌ Found N_ALSyn start but no closing brace.")
    else:
        print("❌ ERROR: Could not find N_ALSyn structure. Manual inspection required.")

if __name__ == '__main__':
    patch_audio_structs()
