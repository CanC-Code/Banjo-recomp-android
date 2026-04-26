import os

def patch_mpi():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    
    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r') as f:
        content = f.read()

    if "#define M_PI" not in content:
        # Provide standard double-precision Pi. 
        # The #ifndef ensures we don't collide if a specific math.h inclusion later defines it.
        injection = """
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
"""
        # Prepend to the very top to ensure it is evaluated immediately
        content = injection + content.lstrip()

        with open(header_path, 'w') as f:
            f.write(content)
        print("✅ Successfully injected M_PI definition into n64_types.h")
    else:
        print("✅ M_PI definition is already present.")

if __name__ == '__main__':
    patch_mpi()
