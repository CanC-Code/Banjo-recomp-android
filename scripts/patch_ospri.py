import os

def patch_ospri():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): return

    with open(header_path, 'r') as f:
        content = f.read()

    # check if OSPri is already defined (via guard or raw text)
    if "OSPri" in content and "BKA_OSPRI_DEFINED" in content:
        print("✅ OSPri already defined. Skipping.")
        return

    injection = """
#ifndef BKA_OSPRI_DEFINED
#define BKA_OSPRI_DEFINED
typedef int OSPri;
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
"""
    # Prepend to the top of the file (after the first include guard)
    first_guard = content.find('_H_')
    if first_guard != -1:
        insert_pos = content.find('\n', first_guard) + 1
        content = content[:insert_pos] + injection + content[insert_pos:]
    else:
        content = injection + content

    with open(header_path, 'w') as f:
        f.write(content)
    print("✅ Applied OSPri/M_PI prepend patch.")

if __name__ == '__main__':
    patch_ospri()
