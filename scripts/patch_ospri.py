import os
import re

def patch_ospri_top_level():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    # 1. Clean up any prior injection attempts to prevent redefinition errors
    # This regex catches both the s32 and int variants from any previous runs
    content = re.sub(r'/\* Injected OSPri.*?\*/\s*typedef\s+(s32|int)\s+OSPri;\s*', '', content, flags=re.DOTALL)
    content = re.sub(r'typedef\s+(s32|int)\s+OSPri;\s*', '', content)

    # 2. Establish the robust top-level injection
    # We define it as standard 'int' to ensure it doesn't fail if 's32' hasn't been parsed yet.
    injection = """#ifndef BKA_OSPRI_DEFINED
#define BKA_OSPRI_DEFINED
/* Injected OSPri for libultra compatibility - placed at top-level to guarantee evaluation */
typedef int OSPri;
#endif

"""
    # 3. Prepend directly to the start of the file, bypassing all include guards
    if "BKA_OSPRI_DEFINED" not in content:
        content = injection + content.lstrip()

        with open(header_path, 'w') as f:
            f.write(content)
        print("✅ Successfully injected top-level OSPri definition into n64_types.h")
    else:
        print("✅ OSPri definition is already present and properly guarded.")

if __name__ == '__main__':
    patch_ospri_top_level()
