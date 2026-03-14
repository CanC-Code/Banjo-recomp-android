#include <cstdint>
#include <cstring>

extern "C" {

// -----------------------------
// CPU / Exception State (Context)
// -----------------------------
// This struct must match the exact binary layout of the libultra OSContext.
// Offsets are critical for compatibility with pre-compiled or HLE logic.
struct CPUState {
    /* 0x00 */ uint64_t at, v0, v1, a0;
    /* 0x20 */ uint64_t a1, a2, a3, t0;
    /* 0x40 */ uint64_t t1, t2, t3, t4;
    /* 0x60 */ uint64_t t5, t6, t7, s0;
    /* 0x80 */ uint64_t s1, s2, s3, s4;
    /* 0xA0 */ uint64_t s5, s6, s7, t8;
    /* 0xC0 */ uint64_t t9, gp, sp, s8; // s8 is the frame pointer ($fp)
    /* 0xE0 */ uint64_t ra, lo, hi;
    /* 0xF8 */ uint32_t status, cause, pc, badvaddr, rcp, fpcsr;
    /* 0x110 */ uint64_t fregs[32]; 
};

typedef struct OSThread_s {
    struct OSThread_s *next;        /* 0x00 */
    int32_t priority;               /* 0x04 */
    struct OSThread_s **queue;      /* 0x08 */
    struct OSThread_s *tnext;       /* 0x0C */
    CPUState context;               /* 0x10 */
} OSThread;

// -----------------------------
// Global Scheduler Symbols
// -----------------------------
OSThread* __osRunningThread = nullptr;
OSThread* __osRunQueue = nullptr;
OSThread* __osFaultedThread = nullptr;
CPUState __osThreadSave; // Used as a temporary buffer during context switches

volatile uint32_t __OSGlobalIntMask = 0xFFFFFFFF;
uintptr_t __osHwIntTable[5] = {0};
uint8_t   __osIntOffTable[32] = {0};

// -----------------------------
// Thread Logic (Ported from .s)
// -----------------------------

void __osEnqueueThread(OSThread** queue, OSThread* thread) {
    OSThread* prev = (OSThread*)queue;
    OSThread* curr = *queue;

    while (curr != nullptr && curr->priority >= thread->priority) {
        prev = curr;
        curr = curr->next;
    }
    thread->next = curr;
    prev->next = thread;
}

OSThread* __osPopThread(OSThread** queue) {
    OSThread* thread = *queue;
    if (thread != nullptr) {
        *queue = thread->next;
    }
    return thread;
}

void __osDispatchThread() {
    __osRunningThread = __osPopThread(&__osRunQueue);
    __osRunningThread->context.status |= 0x0001; // Enable "interrupts" in fake SR
    
    // In a port, we don't 'eret'. This function usually returns 
    // to a wrapper that executes the thread's function pointer.
}

void __osEnqueueAndYield(OSThread** queue) {
    // Save current state if necessary (handled by the HLE engine usually)
    if (__osRunningThread != nullptr) {
        if (queue != nullptr) {
            __osEnqueueThread(queue, __osRunningThread);
        }
    }
    __osDispatchThread();
}

// -----------------------------
// Interrupt Handling
// -----------------------------

void redispatch() {
    if (__osRunningThread != nullptr) {
        __osEnqueueThread(&__osRunQueue, __osRunningThread);
    }
    __osDispatchThread();
}

// The RCP handler in assembly checks MI_INTR_REG to see what caused the IRQ
// In HLE, we call this when the Audio/Graphics task finishes.
void handleRCP() {
    // Porting Note: You should call __osDispatchEvent(OS_EVENT_SP/DP/VI) 
    // here based on which RCP task just completed.
    redispatch();
}

// -----------------------------
// Initialization
// -----------------------------

void initInterruptTables() {
    // Maps the MIPS Cause register IP bits to the handler offsets in __osIntTable
    static const uint8_t defaultOffsets[32] = {
        0, 20, 24, 24, 28, 28, 28, 28, 32, 32, 24, 24, 28, 28, 28, 28,
        0, 4, 8, 8, 12, 12, 12, 12, 16, 16, 16, 16, 16, 16, 16, 16
    };
    std::memcpy((void*)__osIntOffTable, defaultOffsets, 32);
}

} // extern "C"
