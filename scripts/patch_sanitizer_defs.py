import os

def patch_sanitizer_definitions():
    """
    Injects definitions for sanitized tokens (n64_bool, n64_malloc, etc.)
    into the master n64_types.h header.
    """
    header_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    if not os.path.exists(header_path):
        print(f"❌ ERROR: File not found: {header_path}")
        return

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check for the cooperative guard to avoid double-injection
    if "BKA_SANITIZER_SUPPORT_DEFINED" in content:
        print("✅ Sanitizer definitions already present. Skipping.")
        return

    sanitizer_block = """
#ifndef BKA_SANITIZER_SUPPORT_DEFINED
#define BKA_SANITIZER_SUPPORT_DEFINED

/* BKA SANITIZER SUPPORT */
typedef s32 n64_bool;

#ifndef n64_malloc
    #define n64_malloc  malloc
    #define n64_free    free
    #define n64_realloc realloc
    #define n64_calloc  calloc
    #define n64_printf  printf
    #define n64_sprintf sprintf
    #define n64_memcpy  memcpy
    #define n64_memmove memmove
    #define n64_strlen  strlen
    #define n64_strcpy  strcpy
    #define n64_strcat  strcat
    #define n64_sin     sin
    #define n64_cos     cos
#endif

#endif /* BKA_SANITIZER_SUPPORT_DEFINED */
"""

    # Find the final #endif of the include guard to keep the file valid
    last_endif_idx = content.rfind('#endif')
    
    if last_endif_idx != -1:
        new_content = content[:last_endif_idx] + sanitizer_block + "\n" + content[last_endif_idx:]
    else:
        # Fallback if guards are missing
        new_content = content + sanitizer_block

    with open(header_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("✅ Successfully injected sanitizer support definitions into n64_types.h")

if __name__ == '__main__':
    patch_sanitizer_definitions()
