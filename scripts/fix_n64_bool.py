import os

def create_n64_bool():
    filepath = 'Android/app/src/main/cpp/ultra/n64_bool.h'
    print(f"🔧 Creating missing header: {filepath}...")
    
    # Standard C boolean definitions safely wrapped
    content = """#ifndef N64_BOOL_H
#define N64_BOOL_H

#ifndef __cplusplus
#include <stdbool.h>
#endif

#ifndef TRUE
#define TRUE 1
#endif

#ifndef FALSE
#define FALSE 0
#endif

#endif // N64_BOOL_H
"""
    # Ensure the directory exists just in case
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("✅ n64_bool.h created successfully!")

if __name__ == '__main__':
    create_n64_bool()
