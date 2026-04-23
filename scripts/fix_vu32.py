import os

def patch_n64_types(filepath):
    print(f"🔧 Checking {filepath} for missing N64 volatile types...")
    
    if not os.path.exists(filepath):
        print(f"❌ Could not find {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if vu32 is already in the file to avoid appending multiple times
    if "vu32" not in content:
        new_types = """
// --- AUTO-INJECTED N64 VOLATILE TYPES ---
typedef volatile uint8_t   vu8;
typedef volatile int8_t    vs8;
typedef volatile uint16_t  vu16;
typedef volatile int16_t   vs16;
typedef volatile uint32_t  vu32;
typedef volatile int32_t   vs32;
typedef volatile uint64_t  vu64;
typedef volatile int64_t   vs64;
"""
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(new_types)
        print("✅ Successfully injected vu32 and other volatile types!")
    else:
        print("⚡ Types already exist, skipping.")

if __name__ == '__main__':
    # The path to the header as seen in your compiler logs
    patch_n64_types('Android/app/src/main/cpp/ultra/n64_types.h')
