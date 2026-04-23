import os
import re

def hoist_function_pointers(directory):
    print(f"🔍 Hoisting function pointer typedefs in {directory}...")
    match_count = 0
    
    # Matches function pointer typedefs like: typedef void (*Method_X)(int arg);
    fn_ptr_pattern = re.compile(r'typedef\s+[a-zA-Z0-9_ \t\n\r\*]+\(\s*\*\s*[a-zA-Z0-9_]+\s*\)\s*\([^;{]*\)\s*;')
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.c') or file.endswith('.h'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                pointers = fn_ptr_pattern.findall(content)
                if pointers:
                    pointers = [p.strip() for p in pointers]
                    
                    # Remove the typedefs from their original locations
                    new_content = fn_ptr_pattern.sub('', content)
                    
                    # Hoist them into a block
                    hoisted_str = "\n/* AUTO-HOISTED FUNCTION POINTERS */\n" + "\n".join(pointers) + "\n\n"
                    
                    # Insert right after the last #include (which puts them ABOVE our hoisted structs!)
                    insert_pos = 0
                    includes = list(re.finditer(r'#include\s+.*?\n', new_content))
                    if includes:
                        insert_pos = includes[-1].end()
                        
                    new_content = new_content[:insert_pos] + hoisted_str + new_content[insert_pos:]
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    match_count += 1
                    print(f"  🏗️ Hoisted {len(pointers)} function pointers in {filepath}")

    print(f"✅ Finished hoisting function pointers in {match_count} files.")

if __name__ == '__main__':
    hoist_function_pointers('src')
