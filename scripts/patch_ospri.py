import os

def patch_ospri():
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'
    if not os.path.exists(header_path): 
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # check if already defined via guard
    if "BKA_OSPRI_DEFINED" in content:
        print("✅ M_PI and OSPri handlers already applied. Skipping.")
        return

    injection = """
/* =========================
   MATH CONSTANTS
   ========================= */
#ifndef BKA_OSPRI_DEFINED
#define BKA_OSPRI_DEFINED

/* NOTE: OSPri is natively provided by PR/os.h via our master include list, 
 * so the manual typedef has been removed to prevent Clang redefinition errors.
 */

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#endif /* BKA_OSPRI_DEFINED */
"""
    # Safely insert BEFORE the final master #endif instead of blindly prepending
    last_endif = content.rfind('#endif')
    if last_endif != -1:
        content = content[:last_endif] + injection + "\n" + content[last_endif:]
    else:
        content += injection

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("✅ Applied M_PI patch (OSPri safely delegated to SDK).")

if __name__ == '__main__':
    patch_ospri()
