#ifndef N64_TYPES_H
#define N64_TYPES_H

#ifndef _LANGUAGE_C
#define _LANGUAGE_C
#endif

// Prevent N64 SDK from defining its own conflicting types
#define _ULTRATYPES_H_

#include <stdint.h>
#include <stddef.h>
#include <math.h> // Include system math first

// --- Basic N64 Types ---
typedef uint8_t   u8;
typedef uint16_t  u16;
typedef uint32_t  u32;
typedef uint64_t  u64;
typedef int8_t    s8;
typedef int16_t   s16;
typedef int32_t   s32;
typedef int64_t   s64;
typedef float     f32;
typedef double    f64;

typedef s32       n64_bool;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

// --- Graphics & Math Types (Required by gu.h) ---
// N64 Matrices are 512-bit fixed point arrays
typedef s32 Mtx_t[4][4];
typedef union {
    Mtx_t       m;
    long long   force_structure_alignment;
} Mtx;

// Gfx is the N64 Display List command (64-bit)
typedef struct {
    uint32_t words[2];
} Gfx;

// Other Gfx-related types expected by headers
typedef struct { u32 words[2]; } Vp;
typedef struct { u32 words[2]; } LookAt;
typedef struct { u32 words[2]; } Hilite;

// --- Audio Types (Required by libaudio.h) ---
// Acmd is the Audio Command (64-bit)
typedef struct {
    uint32_t words[2];
} Acmd;

// ADPCM state is used for samples
typedef s16 ADPCM_STATE[16];

// --- Core N64 OS Structures (HLE Definitions) ---
typedef void * OSMesg;

typedef struct OSMesgQueue_s {
    void* mtqueue;
    void* fullqueue;
    s32           validCount;
    s32           first;
    s32           msgCount;
    OSMesg* msg;
} OSMesgQueue;

typedef struct OSIoMesg_s {
    void* hdr;
    void* dramAddr;
    u32           devAddr;
    u32           size;
    OSMesgQueue* retQueue;
} OSIoMesg;

typedef struct OSPiHandle_s {
    u8            type;
    u32           baseAddress;
    u32           latency;
    u32           pulse;
    u32           pageSize;
    u32           relDuration;
    u32           domain;
} OSPiHandle;

// --- Bridge Structure ---
#ifdef __cplusplus
extern "C" {
#endif

#include <ultra64.h>
#include <PR/sched.h>

typedef struct {
    uint32_t* screenBuffer;
    uint32_t frameCount;
} AndroidBridgeGlobals;

#ifdef __cplusplus
}
#endif

// Restore legacy N64 NULL definition for float initializers
#undef NULL
#define NULL 0

#endif // N64_TYPES_H
