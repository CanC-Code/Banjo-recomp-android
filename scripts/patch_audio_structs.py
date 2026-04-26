import os
import re

def patch_audio_structs():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'sv_dramout' in content:
        print("⏭️ sv_dramout already exists. Skipping.")
        return

    print("🛠️ Attempting aggressive patch for N_ALSyn structure...")
    
    # Strategy: Find the start of the N_ALSyn structure and inject the member.
    # We look for the start of the struct, then find the next closing brace.
    struct_start = re.search(r'struct\s+(N_ALSyn_s|N_ALSyn)\s*\{', content)
    
    if struct_start:
        start_pos = struct_start.end()
        # Find the end of this specific struct block
        # (Assuming no nested structs with braces, which is standard for N64 audio)
        end_brace_pos = content.find('}', start_pos)
        
        if end_brace_pos != -1:
            new_content = (
                content[:end_brace_pos] + 
                "    int sv_dramout; /* Added for Banjo Save routine */\n" + 
                content[end_brace_pos:]
            )
            with open(header_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("✅ Successfully injected sv_dramout into N_ALSyn.")
        else:
            print("❌ Could not find closing brace for N_ALSyn.")
    else:
        print("❌ Could not find N_ALSyn structure definition.")

if __name__ == '__main__':
    patch_audio_structs()
