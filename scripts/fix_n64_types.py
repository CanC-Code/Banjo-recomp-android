import os

def fix_n64_types():
    filepath = 'Android/app/src/main/cpp/ultra/n64_types.h'
    print(f"🔧 Hardening N64 SDK types in {filepath}...")
    
    content = """#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>

// Basic N64 Fixed-Width Types
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

typedef volatile uint8_t   vu8;
typedef volatile int8_t    vs8;
typedef volatile uint16_t  vu16;
typedef volatile int16_t   vs16;
typedef volatile uint32_t  vu32;
typedef volatile int32_t   vs32;
typedef volatile uint64_t  vu64;
typedef volatile int64_t   vs64;

// --- Graphics & Audio Primitives ---
// These are needed by PR/libaudio.h and PR/gu.h
typedef uint64_t Acmd;
typedef uint64_t Gfx;
typedef int32_t  Mtx_t[4][4];
typedef struct { Mtx_t m; } Mtx;

typedef struct { s16 data[16]; } ADPCM_STATE;
typedef struct { u8 data[64]; }  LookAt;
typedef struct { u8 data[64]; }  Hilite;
typedef struct { u8 data[128]; } Image;

// --- SDK Handles (Guarded to prevent redefinition) ---

#ifndef _OS_H_
typedef void* OSMesg;

typedef struct {
    u32 valid;
    u32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct OSIoMesg_s {
    OSMesg      hdr;
    u32         devAddr;
    void        *dramAddr;
    u32         size;
    OSMesgQueue *retQueue;
} OSIoMesg;

typedef struct {
    u32 type;
    u32 baseAddr;
    u32 latency;
    u32 pulse;
    u32 pageSize;
    u32 relDuration;
} OSPiHandle;
#endif

#ifndef _AL_H_
typedef struct {
    u8 data[1024]; 
} ALGlobals;
#endif

// Boolean definitions
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
        
    print("✅ n64_types.h updated with guarded SDK primitives!")

if __name__ == '__main__':
    fix_n64_types()
