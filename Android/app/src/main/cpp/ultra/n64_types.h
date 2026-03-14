#ifndef N64_TYPES_H
#define N64_TYPES_H

#include <stdint.h>
#include <stddef.h>

typedef int8_t s8;   typedef uint8_t u8;
typedef int16_t s16; typedef uint16_t u16;
typedef int32_t s32; typedef uint32_t u32;
typedef int64_t s64; typedef uint64_t u64;
typedef float f32;   typedef double f64;

#ifdef __cplusplus
extern "C" {
#endif

// Exact binary layout of the N64 CPU Context
typedef struct {
    /* 0x00 */ uint64_t at, v0, v1, a0;
    /* 0x20 */ uint64_t a1, a2, a3, t0;
    /* 0x40 */ uint64_t t1, t2, t3, t4;
    /* 0x60 */ uint64_t t5, t6, t7, s0;
    /* 0x80 */ uint64_t s1, s2, s3, s4;
    /* 0xA0 */ uint64_t s5, s6, s7, t8;
    /* 0xC0 */ uint64_t t9, gp, sp, s8; 
    /* 0xE0 */ uint64_t ra, lo, hi;
    /* 0xF8 */ uint32_t status, cause, pc, badvaddr, rcp, fpcsr;
    /* 0x110 */ uint64_t fregs[32];
} CPUState;

typedef struct OSThread_s {
    struct OSThread_s *next;        /* 0x00 */
    int32_t priority;               /* 0x04 */
    struct OSThread_s **queue;      /* 0x08 */
    struct OSThread_s *tnext;       /* 0x0C */
    CPUState context;               /* 0x10 */
} OSThread;

typedef void* OSMesg;
typedef struct { void* mt; void* full; int32_t count; } OSMesgQueue;

#ifdef __cplusplus
}
#endif

#define _ULTRATYPES_H_
#define _OS_THREAD_H_
#endif
