import os

def patch_missing_macros(filepath):
    print(f"🔧 Checking {filepath} for missing N64 graphics macros...")
    
    if not os.path.exists(filepath):
        print(f"❌ Could not find {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if G_TRI2 is already injected
    if "G_TRI2" not in content:
        new_macros = """
// --- AUTO-INJECTED MISSING GRAPHICS MACROS ---
#ifndef G_TRI2
#define G_TRI2 0xb1
#endif
"""
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(new_macros)
        print("✅ Successfully injected G_TRI2 macro!")
    else:
        print("⚡ Macros already exist, skipping.")

if __name__ == '__main__':
    # The path to the global header
    patch_missing_macros('Android/app/src/main/cpp/ultra/n64_types.h')
