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

/**
 * 4. N64 OS TYPES (FOUNDATION)
 */
#define OS_NUM_EVENTS 15
typedef u32 OSEvent;
typedef u64 OSTime;
typedef void* OSMesg;
typedef void* OSTask;

typedef u32 OSIntMask;
#define OS_IM_NONE 0

#define OS_MESG_BLOCK 1
#define OS_MESG_NOBLOCK 0

// FIX: Shielded global variable from C++ name mangling!
#ifdef __cplusplus
extern "C" {
#endif
extern u32 osTvType;
#ifdef __cplusplus
}
#endif

#define OS_TV_NTSC 0
#define OS_TV_PAL 1
#define OS_TV_MPAL 2

#define PFS_ERR_DEVICE 11
#define PFS_ERR_ID_FATAL 12

typedef struct OSMesgQueue_s {
    void* mt;
    void* full;
    s32 count;
} OSMesgQueue;

typedef struct {
    u16 type;
    u8 pri;
    u8 cmp;
    OSMesgQueue *retQueue;
} OSIoMesgHdr;

typedef struct {
    OSIoMesgHdr hdr;
    void *dramAddr;
    u32 devAddr;
    u32 size;
    void *piHandle; 
} OSIoMesg;

typedef struct {
    int queue;
    int channel;
    u8 id[32];
    u8 label[32];
    int version;
    int dir_size;
    int inode_table;
    int minode_table;
    int dir_table;
    int inode_start_page;
    u8 banks;
    u8 activebank;
} OSPfs;

typedef struct {
    u64 registers[32];
    u64 lo, hi, pc;
    u32 status, cause, badvaddr;
} CPUState;

typedef struct OSThread_s {
    struct OSThread_s *next;
    OSPri priority;
    CPUState context;
    u8 padding[512];
} OSThread;

typedef struct { u16 button; s8 stick_x, stick_y; u8 errnum; } OSContPad;
typedef struct { u16 type; u8 status, errnum; } OSContStatus;

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

#ifndef UNITY_PITCH
  #define UNITY_PITCH 0x8000
#endif

#ifndef MAX_RATIO
  #define MAX_RATIO 1.99996
#endif

typedef struct { short ob[3]; unsigned short flag; short tc[2]; unsigned char cn[4]; } Vtx_t;
typedef union { Vtx_t v; long long force_align; } Vtx;
typedef union { struct { s32 m[4][4]; }; long long force_align; } Mtx;

typedef struct { unsigned char col[3], pad1; unsigned char colc[3], pad2; signed char dir[3], pad3; } Light_t;
typedef union { Light_t l; long long force_align[2]; } Light;
typedef struct { Light l[2]; } LookAt;

/**
 * 6. RECOMPILATION SPECIFIC TYPES
 */
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

/**
 * FIX: Define NULL as 0 AFTER system headers. 
 */
#undef NULL
#define NULL 0

#ifndef M_PI
  #define M_PI 3.14159265358979323846
#endif

#ifdef __cplusplus
extern "C" {
#endif

/**
 * 8. N64 SDK INCLUDES
 */
#include <PR/libaudio.h>

/**
 * 9. POLYFILLS
 */
static inline int sched_yield_polyfill(void) { return usleep(1); }
#undef sched_yield
#define sched_yield sched_yield_polyfill

#ifdef __cplusplus
}
#endif

#endif
