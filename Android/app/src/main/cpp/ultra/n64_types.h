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
 * 3. SYSTEM & SDK INCLUDES (Foundation)
 */
#include <sys/types.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>
#include <math.h>
#include <unistd.h>
#include <sched.h>  // Authority for sched_yield

/**
 * 4. CORE N64 SCALARS
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
 * 5. N64 OS TYPES (FOUNDATION)
 */
#define OS_NUM_EVENTS 15
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

typedef union {
    OSTask_t t;
    long long int force_align[32];
} OSTask;

typedef volatile u32 OSIntMask;
#define OS_IM_NONE 0
#define OS_MESG_BLOCK 1
#define OS_MESG_NOBLOCK 0

/**
 * 6. OS STRUCTURES
 */
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

typedef struct OSMesgQueue_s {
    struct OSThread_s *mtqueue;
    struct OSThread_s *fullqueue;
    s32 validCount;
    s32 first;
    s32 msgCount;
    OSMesg *msg;
} OSMesgQueue;

typedef struct OSTimer_s {
    struct OSTimer_s *next;
    struct OSTimer_s *prev;
    u64 interval;
    u64 value;
    OSMesgQueue *mq;
    OSMesg msg;
} OSTimer;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    struct OSMesgQueue_s *queue;
    OSMesg msg;
    u32 contextId;
    u32 state;
    u32 flags;
    OSId id;
    int fp;
    CPUState context;
    struct OSThread_s *tlnext; 
    struct OSThread_s *tlprev;
} OSThread;

typedef struct {
    u16 type;
    u8 pri;
    u8 cmp;
    OSMesgQueue *retQueue;
} OSIoMesgHdr;

typedef struct OSPiHandle_s {
    struct OSPiHandle_s *next;
    u8 type;
    u8 latency;
    u8 pageSize;
    u8 relDuration;
    u8 pulse;
    u8 domain;
    u32 baseAddress;
    u32 speed;
} OSPiHandle;

typedef struct {
    OSIoMesgHdr hdr;
    void *dramAddr;
    u32 devAddr;
    u32 size;
    OSPiHandle *piHandle; 
} OSIoMesg;

/**
 * 7. INPUT Foundation
 */
typedef struct { u16 button; s8 stick_x, stick_y; u8 errno; } OSContPad;
typedef struct { u16 type; u8 status, errno; } OSContStatus;

/**
 * 8. GRAPHICS & SDK TYPES
 */
typedef u64 Gfx;
typedef u64 Acmd;
typedef s16 ADPCM_STATE[16];
typedef s16 POLEF_STATE[16];
typedef s16 RESAMPLE_STATE[16];
typedef s16 ENVMIX_STATE[40];

typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef union { Vtx_t v; long long force_align; } Vtx;
typedef union { struct { s32 m[4][4]; }; long long force_align; } Mtx;

#ifdef __cplusplus
extern "C" {
#endif
extern u32 osTvType;
extern OSTime osClockRate;
extern u32 osRomBase;
extern u32 osResetType;
extern u32 osAppNMIBuffer;
extern OSIntMask __OSGlobalIntMask;

extern void guMtxIdentF(float mf[4][4]);
extern void guMtxF2L(float mf[4][4], Mtx *m);

#include <PR/libaudio.h>
#include <PR/os_cont.h>
#ifdef __cplusplus
}
#endif

/**
 * 9. GAME-SPECIFIC TAG HARMONIZATION
 */
typedef struct actor_s Actor;
typedef struct actorMarker_s ActorMarker;
typedef struct ch_vegatable sChVegetable;
typedef struct LetterFloorTile LetterFloorTile;
typedef struct ActorLocal_Lockup ActorLocal_Lockup;

#endif
