import os

def fix_n64_types():
    filepath = 'Android/app/src/main/cpp/ultra/n64_types.h'
    print(f"🔧 Expanding N64 types and SDK structures in {filepath}...")
    
    content = """#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>

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

// Volatile variants
typedef volatile uint8_t   vu8;
typedef volatile int8_t    vs8;
typedef volatile uint16_t  vu16;
typedef volatile int16_t   vs16;
typedef volatile uint32_t  vu32;
typedef volatile int32_t   vs32;
typedef volatile uint64_t  vu64;
typedef volatile int64_t   vs64;

// SDK Handles and Dummy Structs
// These satisfy 'unknown type' and 'sizeof' errors in the emulator layer
typedef void* OSMesg;

typedef struct {
    u32 valid;
} OSMesgQueue;

typedef struct {
    u32 valid;
} OSIoMesg;

typedef struct {
    u32 valid;
} OSPiHandle;

typedef struct {
    u32 valid;
} OSThread;

// Audio Library Globals
typedef struct {
    u8 data[1024]; // Generic buffer for ALGlobals
} ALGlobals;

// Boolean type
#ifndef N64_BOOL_DEFINED
#define N64_BOOL_DEFINED
typedef int n64_bool;
#define TRUE  1
#define FALSE 0
#endif

#endif // N64_TYPES_H
"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("✅ n64_types.h updated with SDK structures!")

if __name__ == '__main__':
    fix_n64_types()
