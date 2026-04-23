import os

def fix_n64_types():
    # This is the path the compiler is looking at via the -include flag
    filepath = 'Android/app/src/main/cpp/ultra/n64_types.h'
    print(f"🔧 Ensuring comprehensive N64 types in {filepath}...")
    
    # Standard N64 types used throughout the Banjo codebase
    content = """#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>

// Basic Types
typedef uint8_t   u8;
typedef int8_t    s8;
typedef uint16_t  u16;
typedef int16_t   s16;
typedef uint32_t  u32;
typedef int32_t   s32;
typedef uint64_t  u64;
typedef int64_t   s64;

typedef float     f32;
typedef double    f64;

// Volatile variants (for hardware registers)
typedef volatile uint8_t   vu8;
typedef volatile int8_t    vs8;
typedef volatile uint16_t  vu16;
typedef volatile int16_t   vs16;
typedef volatile uint32_t  vu32;
typedef volatile int32_t   vs32;
typedef volatile uint64_t  vu64;
typedef volatile int64_t   vs64;

typedef volatile float     vf32;
typedef volatile double    vf64;

// Boolean type often used in the N64 SDK
#ifndef N64_BOOL_DEFINED
#define N64_BOOL_DEFINED
typedef int n64_bool;
#define TRUE  1
#define FALSE 0
#endif

#endif // N64_TYPES_H
"""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("✅ n64_types.h is now fully populated!")

if __name__ == '__main__':
    fix_n64_types()
