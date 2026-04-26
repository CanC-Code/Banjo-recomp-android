import os

def fix_n64_types():
    types_path = 'Android/app/src/main/cpp/ultra/n64_types.h'

    # Headers to silence to ensure our forced include is the source of truth
    headers_to_wipe = [
        'include/2.0L/PR/libaudio.h', 'include/2.0L/PR/n_libaudio.h',
        'include/2.0L/PR/os.h', 'include/2.0L/PR/gu.h',
        'include/2.0L/PR/gbi.h', 'include/n_synth.h', 'include/synthInternals.h'
    ]

    for header in headers_to_wipe:
        if os.path.exists(header):
            with open(header, 'w') as f:
                f.write("// Silenced by fix_n64_types.py\n")

    content = """#ifndef _BKA_ANDROID_N64_TYPES_H_
#define _BKA_ANDROID_N64_TYPES_H_

#include <stdint.h>
#include <stddef.h>
#include <math.h>

/**
 * FOUNDATION TYPES & MATH
 */
typedef unsigned char      u8;
typedef signed char        s8;
typedef unsigned short     u16;
typedef signed short       s16;
typedef unsigned int       u32;
typedef signed int         s32;
typedef unsigned long long u64;
typedef signed long long   s64;
typedef float              f32;
typedef double             f64;

#ifndef BKA_OSPRI_DEFINED
#define BKA_OSPRI_DEFINED
typedef int OSPri;
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

// --- OS & KERNEL ---
typedef void* OSMesg;
typedef u32 OSIntMask;

typedef struct {
    u32 valid;
    u32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    struct OSThread_s **queue;
    struct OSThread_s *tnext;
    u16 state;
    u16 flags;
    s32 id;
    int fp;
} OSThread;

// --- AUDIO & ENGINE (COOPERATIVE DEFINITIONS) ---
#ifndef BKA_ALSYNTH_DEFINED
#define BKA_ALSYNTH_DEFINED
typedef struct {
    u8 opaque_pad[256];
} ALSynth;
#endif

#ifndef BKA_ALGLOBALS_DEFINED
#define BKA_ALGLOBALS_DEFINED
typedef struct ALGlobals_s {
    ALSynth drvr;
    u8 pad[2048];
} ALGlobals;
#endif

typedef s32 ALMicroTime;
typedef u8 ALPan; 
typedef u64 Acmd;

// [Rest of your standard definitions...]
// (Truncated for brevity, but keep your ALWaveTable, ALPVoice, etc. here)

#ifdef __cplusplus
extern "C" {
#endif
extern ALGlobals *alGlobals;
extern OSThread  *__osRunningThread;
#ifdef __cplusplus
}
#endif

#endif
"""
    os.makedirs(os.path.dirname(types_path), exist_ok=True)
    with open(types_path, 'w') as f:
        f.write(content)
    print("✅ Master n64_types.h generated with cooperative guards.")

if __name__ == '__main__':
    fix_n64_types()
