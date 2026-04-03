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
 * 4. N64 OS TYPES (FOUNDATION)
 */
#define OS_NUM_EVENTS 15
typedef u32 OSEvent;
typedef u64 OSTime;
typedef void* OSMesg;

typedef struct {
    u32 type;
    u32 flags;
    u64 *ucode_boot;
    u32 ucode_boot_size;
    u64 *ucode;
    u32 ucode_size;
    u64 *ucode_data;
    u32 ucode_data_size;
    u64 *dram_stack;
    u32 dram_stack_size;
    u64 *output_buff;
    u64 *output_buff_size;
    u64 *data_ptr;
    u32 data_size;
    u64 *yield_data_ptr;
    u32 yield_data_size;
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
 * 5. GRAPHICS & AUDIO TYPES
 */
typedef u64 Gfx;
typedef u64 Acmd;

typedef s16 ADPCM_STATE[16];
typedef s16 POLEF_STATE[16];
typedef s16 RESAMPLE_STATE[16];
typedef s16 ENVMIX_STATE[40];

#define ADPCMFSIZE 9
#define ADPCMVSIZE 8

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

#ifdef __cplusplus
}
#endif

/**
 * 6. GAME-SPECIFIC BASE TYPES
 */
typedef struct Actor Actor;
typedef struct ActorMarker ActorMarker;
typedef struct ch_vegatable sChVegetable;

/**
 * 7. SYSTEM INCLUDES
 */
#include <sys/types.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>
#include <math.h>
#include <unistd.h>

#ifdef __cplusplus
extern "C" {
#endif
#include <PR/libaudio.h>
#ifdef __cplusplus
}
#endif

#endif
