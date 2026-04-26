import os
import re

def hoist_function_pointers(directory):
    print(f"🔍 Hoisting and Syncing function pointer typedefs in {directory}...")
    
    # These are already defined in our Master n64_types.h
    # We must REMOVE these from source files to prevent redefinition errors.
    GLOBAL_KNOWN_PTRS = [
        'ALDMAproc', 'ALDMANew', 'ALOscInit', 'ALOscUpdate', 
        'ALOscStop', 'ALCmdHandler', 'ALSetParam', 
        'ALSetFXParam', 'N_ALCmdHandler'
    ]

    # Pattern to match typedef function pointers
    fn_ptr_pattern = re.compile(r'typedef\s+[a-zA-Z0-9_ \t\n\r\*]+\(\s*\*\s*([a-zA-Z0-9_]+)\s*\)\s*\([^;{]*\)\s*;')

    match_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.c', '.h')):
                filepath = os.path.join(root, file)
                
                # Skip our own ultra headers to avoid self-sabotage
                if 'ultra' in filepath: continue

                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                new_lines = []
                hoisted_locals = []
                changed = False

                for line in lines:
                    match = fn_ptr_pattern.search(line)
                    if match:
                        ptr_name = match.group(1)
                        changed = True
                        
                        if ptr_name in GLOBAL_KNOWN_PTRS:
                            # 1. It's a global: Delete it (don't add to new_lines or hoisted)
                            print(f"  🗑️ Removed global redefinition: {ptr_name} in {file}")
                            continue
                        else:
                            # 2. It's a local: Save for hoisting
                            hoisted_locals.append(line.strip())
                            continue
                    
                    new_lines.append(line)

                if changed:
                    # Reconstruct the file
                    content = "".join(new_lines)
                    
                    if hoisted_locals:
                        hoisted_str = "\n/* BKA AUTO-HOISTED LOCAL FUNCTION POINTERS */\n" + \
                                     "\n".join(hoisted_locals) + "\n\n"
                        
                        # Find the best insertion point (after last include)
                        insert_pos = 0
                        includes = list(re.finditer(r'#include\s+.*?\n', content))
                        if includes:
                            insert_pos = includes[-1].end()
                        
                        content = content[:insert_pos] + hoisted_str + content[insert_pos:]

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    match_count += 1

    print(f"✅ Finished syncing function pointers in {match_count} files.")

if __name__ == '__main__':
    # Targeting the src folder where the game logic lives
    hoist_function_pointers('src')
