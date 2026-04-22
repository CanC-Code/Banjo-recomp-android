#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>

// Basic Types
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int8_t s8;
typedef int16_t s16;
typedef int32_t s32;
typedef int64_t s64;
typedef float f32;
typedef double f64;

// Stub complex types to satisfy compiler during verification
#ifdef NO_GAME_SRC
    typedef struct { u32 data[32]; } OSThread;
    typedef struct { u32 data[32]; } CPUState;
    typedef struct { u32 data[2]; }  Acmd;
    typedef struct { u32 data[2]; }  Gfx;
    typedef struct { u32 data[16]; } Mtx;
    typedef struct { u32 data[8]; }  ADPCM_STATE;
    
    // Stub the alGlobals pointer
    typedef struct { u8 dummy; } ALGlobals;
    #ifndef AL_GLOBALS_DEFINED
        #define AL_GLOBALS_DEFINED
        extern ALGlobals* alGlobals;
    #endif
#endif

#endif
