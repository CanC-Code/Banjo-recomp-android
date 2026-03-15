import os
import re
import sys

TARGET_DIRS = ["src", "include"]

def patch_arrays(root_path):
    print("🛠️ Starting Invalid Array Initialization Patch...")
    
    # Matches patterns like: u8 tmp[6] = D_80390DA0;
    # Groups: (1:Type) (2:VarName) (3:ArraySize) (4:DataSource)
    pattern = re.compile(r'\b(u8|s8|u16|s16|u32|s32|f32|int|char|short|long|float|double)\s+([a-zA-Z0-9_]+)\[(\d+)\]\s*=\s*([a-zA-Z0-9_]+)\s*;')
    
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
                
                # Rewrites "u8 tmp[6] = D_80390DA0;" 
                # Into "u8 tmp[6]; memcpy(tmp, D_80390DA0, 6 * sizeof(u8));"
                replacement = r'\1 \2[\3]; memcpy(\2, \4, \3 * sizeof(\1));'
                content = pattern.sub(replacement, content)
                
                if content != original_content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    patch_count += 1
                    print(f"  [Fixed Array] {filepath}")

    print(f"✅ Array patch complete! Modified {patch_count} files.")

if __name__ == "__main__":
    root_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    patch_arrays(root_dir)
