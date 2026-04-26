import os

def patch_missing_macros(filepath):
    """
    Injects missing N64 graphics macros required by the recompilation engine.
    Ensures injection occurs inside the main include guards without colliding
    with PR/gbi.h.
    """
    print(f"🔧 Checking {filepath} for missing N64 graphics macros...")

    if not os.path.exists(filepath):
        print(f"❌ Could not find {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # If the cooperative guard is already there, we are done.
    if "BKA_MISSING_MACROS_DEFINED" in content:
        print("✅ Macros already exist, skipping.")
        return

    # Add G_TRI2 and any other common missing opcodes used in recomp
    macro_block = """
/* =========================
   RECOMPILATION OPCODE EXTENSIONS
   ========================= */
#ifndef BKA_MISSING_MACROS_DEFINED
#define BKA_MISSING_MACROS_DEFINED

#ifndef G_TRI2
    #define G_TRI2 0xb1
#endif

#ifndef G_QUAD
    #define G_QUAD 0xb5
#endif

#endif /* BKA_MISSING_MACROS_DEFINED */
"""

    # Find the last #endif to ensure we stay inside the file's include guard
    last_endif_idx = content.rfind('#endif')

    if last_endif_idx != -1:
        new_content = content[:last_endif_idx] + macro_block + "\n" + content[last_endif_idx:]
    else:
        # Fallback if the file is missing guards entirely
        new_content = content + macro_block

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("✅ Successfully injected missing graphics macros inside guards!")

if __name__ == '__main__':
    # Targeting the harmonized header
    patch_missing_macros('Android/app/src/main/cpp/ultra/n64_types.h')
