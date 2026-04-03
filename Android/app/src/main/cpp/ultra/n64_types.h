#ifndef N64_TYPES_H
#define N64_TYPES_H

/**
 * 1. MANDATORY FEATURE MACROS
 */
#define _POSIX_C_SOURCE 200809L
#define _GNU_SOURCE
#define _USE_MATH_DEFINES

/**
 * 2. THE NUCLEAR BLOCKADE
 */
#define _OS_H_
#define _ULTRA64_H_
#define _GBI_H_
#define _GU_H_

/**
 * 3. CORE N64 SCALARS
 */
typedef signed char s8;
typedef unsigned char u8;
typedef short s16;
typedef unsigned short u16;
typedef int s32;
typedef unsigned int u32;
typedef long long s64;
typedef unsigned long long u64;
typedef float f32;
typedef double f64;
typedef int n64_bool;
typedef s32 OSPri;
typedef s32 OSId;

/**
 * 4. SYSTEM INCLUDES & POLYFILLS
 */
#include <sys/types.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>
#include <math.h>
#include <unistd.h>

/* Authority: Fix 'sched_yield' for Android NDK C++ STL compatibility */
#ifndef sched_yield
  #define sched_yield() usleep(1)
#endif

/**
 * 5. N64 OS FOUNDATION STRUCTURES
 */
typedef u32 OSEvent;
typedef u64 OSTime;
typedef void* OSMesg;

typedef struct {
    u32 type; u32 flags;
    u64 *ucode_boot; u32 ucode_boot_size;
    u64 *ucode; u32 ucode_size;
    u64 *ucode_data; u32 ucode_data_size;
    u64 *dram_stack; u32 dram_stack_size;
    u64 *output_buff; u64 *output_buff_size;
    u64 *data_ptr; u32 data_size;
    u64 *yield_data_ptr; u32 yield_data_size;
} OSTask_t;

typedef union { OSTask_t t; long long int force_align[32]; } OSTask;

typedef struct {
    u64 at, v0, v1, a0, a1, a2, a3;
    u64 t0, t1, t2, t3, t4, t5, t6, t7;
    u64 s0, s1, s2, s3, s4, s5, s6, s7;
    u64 t8, t9, k0, k1, gp, sp, s8, ra;
    u64 lo, hi, pc;
    union { u32 sr; u32 status; };
    u32 cause, badvaddr, rcp;
    u32 fpcsr;
    f64 fp0,  fp2,  fp4,  fp6,  fp8, fp10, fp12, fp14;
    f64 fp16, fp18, fp20, fp22, fp24, fp26, fp28, fp30;
} CPUState;

typedef struct OSThread_s OSThread;
typedef struct OSMesgQueue_s {
    struct OSThread_s *mtqueue;
    struct OSThread_s *fullqueue;
    s32 validCount;
    s32 first;
    s32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    OSMesgQueue *queue;
    OSMesg msg;
    u32 contextId;
    u32 state;
    u32 flags;
    OSId id;
    int fp;
    CPUState context;
    struct OSThread_s *tlnext;
    struct OSThread_s *tlprev;
};

/**
 * 6. GBI / RSP / OS STUBS
 *
 * _GBI_H_ blocks the real gbi.h and _OS_H_ blocks os.h, but several
 * game headers (model.h, structs.h, prop.h, mlmtx.h, modelRender.h,
 * pfsmanager.h) depend on the types below.  We provide minimal stubs
 * so those headers parse cleanly without dragging in the full N64 SDK.
 *
 * All guards follow the pattern used by the upstream SDK so that if any
 * include path ever resolves the real header first, these stubs are skipped.
 */

/* ── Acmd ─────────────────────────────────────────────────────────────────
 * 64-bit RSP audio command word.  Required by libaudio.h.              */
#ifndef ACMD_DEFINED
#define ACMD_DEFINED
typedef union {
    struct { u32 w0; u32 w1; } words;
    long long int force_align;
} Acmd;
#endif

/* ── ADPCM_STATE ──────────────────────────────────────────────────────────
 * 16-entry s16 predictor-state array.  Required by libaudio.h.         */
#ifndef ADPCM_STATE_DEFINED
#define ADPCM_STATE_DEFINED
typedef s16 ADPCM_STATE[16];
#endif

/* ── Vtx ──────────────────────────────────────────────────────────────────
 * Vertex union used in RSP display lists.
 * Required by: model.h, structs.h, prop.h                              */
#ifndef VTX_DEFINED
#define VTX_DEFINED
typedef union {
    struct {
        s16 ob[3];   /* object-space position x,y,z */
        u16 flag;
        s16 tc[2];   /* texture coords s,t           */
        u8  cn[4];   /* colour/normal r,g,b,a        */
    } v;
    struct {
        s16 ob[3];
        u16 flag;
        s16 tc[2];
        s8  n[3];    /* normal x,y,z                 */
        u8  a;       /* alpha                        */
    } n;
    long long int force_align;
} Vtx;
#endif

/* ── Gfx ──────────────────────────────────────────────────────────────────
 * Display list command word pair.
 * Required by: model.h, structs.h, prop.h, modelRender.h               */
#ifndef GFX_DEFINED
#define GFX_DEFINED
typedef union {
    struct { u32 w0; u32 w1; } words;
    long long int force_align;
} Gfx;
#endif

/* ── Mtx ──────────────────────────────────────────────────────────────────
 * Fixed-point 4x4 matrix (16 x s16 integer + 16 x u16 fraction).
 * Required by: structs.h, prop.h, mlmtx.h, modelRender.h
 * NOTE: the game's structs.h already defines MtxF (float 4x4); Clang
 * suggests MtxF for Mtx, confirming these are two distinct types.      */
#ifndef MTX_DEFINED
#define MTX_DEFINED
typedef struct {
    s16 intPart[4][4];
    u16 fracPart[4][4];
} Mtx;
#endif

/* ── OSContPad ────────────────────────────────────────────────────────────
 * Controller pad state struct.  Normally from os_cont.h, but _OS_H_
 * prevents the os.h chain that os_cont.h depends on from loading fully.
 * Required by: pfsmanager.h (include/core1/pfsmanager.h:64)            */
#ifndef OS_CONT_PAD_DEFINED
#define OS_CONT_PAD_DEFINED
typedef struct {
    u16 button;
    s8  stick_x;
    s8  stick_y;
    u8  errno;
} OSContPad;
#endif

#ifdef __cplusplus
extern "C" {
#endif
extern u32 osTvType;
extern OSTime osClockRate;
extern u32 osResetType;
extern u32 osAppNMIBuffer;
extern volatile u32 __OSGlobalIntMask;

#include <PR/libaudio.h>
#include <PR/os_cont.h>
#ifdef __cplusplus
}
#endif

/**
 * 7. GAME-SPECIFIC TAG HARMONIZATION
 */
typedef struct actor_s Actor;
typedef struct actorMarker_s ActorMarker;

#endif
