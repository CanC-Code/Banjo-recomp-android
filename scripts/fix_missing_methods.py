import os
import re

def fix_missing_methods(directory):
    print(f"🔍 Scanning for missing Method_ types in {directory}...")
    
    # Regex to find usages of Method_ types (like `Method_Core2_999A0_0 unk0;`)
    method_pattern = re.compile(r'\b(Method_[A-Za-z0-9_]+)\b')
    
    match_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.c'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                methods_found = set(method_pattern.findall(content))
                missing_methods = []
                
                for method in methods_found:
                    # If there's no typedef for it in the file, it's missing
                    if not re.search(r'typedef\s+.*?\b' + method + r'\b', content):
                        missing_methods.append(method)
                        
                if missing_methods:
                    missing_methods = sorted(list(set(missing_methods)))
                    
                    # Generate dummy typedefs as generic void function pointers
                    typedefs = "\n/* AUTO-GENERATED MISSING METHOD TYPES */\n"
                    for method in missing_methods:
                        typedefs += f"typedef void (*{method})(void);\n"
                        
                    # Insert safely after the includes
                    insert_pos = 0
                    includes = list(re.finditer(r'#include\s+.*?\n', content))
                    if includes:
                        insert_pos = includes[-1].end()
                        
                    new_content = content[:insert_pos] + typedefs + content[insert_pos:]
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    match_count += 1
                    print(f"  💉 Injected {len(missing_methods)} missing types into {filepath}")

    print(f"✅ Finished patching methods in {match_count} files.")

if __name__ == '__main__':
    fix_missing_methods('src')
