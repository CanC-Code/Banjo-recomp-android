#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>

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

// --- Core N64 OS Structures (HLE Definitions) ---
// We define these here to avoid circular dependencies with original SDK headers.

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
    void* hdr;      // OSThread or similar
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

typedef struct {
    uint32_t* screenBuffer; 
    uint32_t frameCount;
} AndroidBridgeGlobals;

#ifdef __cplusplus
}
#endif

#undef NULL
#define NULL 0

#endif // N64_TYPES_H
