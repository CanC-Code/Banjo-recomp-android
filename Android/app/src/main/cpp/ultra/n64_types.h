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

typedef u32 OSIntMask;
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

#ifdef __cplusplus
extern "C" {
#endif
extern u32 osTvType;
extern u32 osClockRate;

extern void guMtxIdentF(float mf[4][4]);
extern void guMtxF2L(float mf[4][4], Mtx *m);

#ifdef __cplusplus
}
#endif

#define OS_TV_NTSC 0
#define OS_TV_PAL 1
#define OS_TV_MPAL 2

#define PFS_ERR_DEVICE 11
#define PFS_ERR_ID_FATAL 12

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

typedef struct {
    u16 type;
    u8 pri;
    u8 cmp;
    OSMesgQueue *retQueue;
} OSIoMesgHdr;

typedef struct {
    u32 errStatus;
    void *dramAddr;
    void *C2Addr;
    u32 sectorSize;
    u32 C1ErrNum;
    u32 C1ErrSector[4];
} __OSBlockInfo;

typedef struct {
    u32 cmdType;
    u16 transferMode;
    u16 blockNum;
    s32 sectorNum;
    u32 devAddr;
    u32 bmCtlShadow;
    u32 seqCtlShadow;
    __OSBlockInfo block[2];
} __OSTranxInfo;

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
    __OSTranxInfo transferInfo;
} OSPiHandle;

// FIX: Added the N64 OS Device Manager struct
typedef struct {
    s32 active;
    OSThread_s *thread;
    OSMesgQueue *cmdQueue;
    OSMesgQueue *evtQueue;
    OSMesgQueue *acsQueue;
    s32 (*dma)(s32, u32, void *, u32);
    s32 (*edma)(OSPiHandle *, s32, u32, void *, u32);
} OSDevMgr;

typedef struct {
    OSIoMesgHdr hdr;
    void *dramAddr;
    u32 devAddr;
    u32 size;
    OSPiHandle *piHandle; 
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
    u32 ctrl;
    u32 width;
    u32 burst;
    u32 vSync;
    u32 hSync;
    u32 leap;
    u32 hStart;
    u32 xScale;
    u32 vCurrent;
} OSViCommonRegs;

typedef struct {
    u32 origin;
    u32 yScale;
    u32 vStart;
    u32 vBurst;
    u32 vIntr;
} OSViFieldRegs;

typedef struct {
    u8 type;
    OSViCommonRegs comRegs;
    OSViFieldRegs fldRegs[2];
} OSViMode;

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

#undef errno
typedef struct { u16 button; s8 stick_x, stick_y; u8 errno; } OSContPad;
typedef struct { u16 type; u8 status, errno; } OSContStatus;

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
