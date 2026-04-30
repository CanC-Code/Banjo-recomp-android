#include <cstdint>
#include <cstring>
#include "n64_types.h"

/**
 * CPUState Definition
 * We define this here to ensure the compiler sees it before usage.
 * This structure represents the MIPS register state for the recompiled VM.
 */
typedef struct {
    uint64_t pc;
    uint64_t at, v0, v1, a0, a1, a2, a3;
    uint64_t t0, t1, t2, t3, t4, t5, t6, t7;
    uint64_t s0, s1, s2, s3, s4, s5, s6, s7;
    uint64_t t8, t9, k0, k1, gp, sp, s8, ra;
    uint64_t lo, hi;
} CPUState;

extern "C" {

// Global Scheduler Symbols
OSThread* __osRunningThread = nullptr;
OSThread* __osRunQueue = nullptr;
OSThread* __osFaultedThread = nullptr;

// Line 17 fix: CPUState is now defined above
CPUState __osThreadSave; 

// Redefinition fix: Using uint32_t to match the SDK's OSIntMask size
// If you encounter a link error here, you may need to use: extern "C" uint32_t __OSGlobalIntMask;
uint32_t __OSGlobalIntMask = 0xFFFFFFFF;

uintptr_t __osHwIntTable[5] = {0};
uint8_t   __osIntOffTable[32] = {0};

// Enqueue a thread into the priority-based run queue
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

// Pop the highest priority thread from the queue
OSThread* __osPopThread(OSThread** queue) {
    OSThread* thread = *queue;
    if (thread != nullptr) {
        *queue = thread->next;
    }
    return thread;
}

// Switch context to the next thread in the queue
void __osDispatchThread() {
    __osRunningThread = __osPopThread(&__osRunQueue);

    if (__osRunningThread == nullptr) return;

    // Pointer fix: Take the address of the context field ('&') 
    // This allows us to cast the memory location to a uint32_t pointer.
    *(reinterpret_cast<uint32_t*>(&__osRunningThread->context)) |= 0x0001; 
}

void __osEnqueueAndYield(OSThread** queue) {
    if (__osRunningThread != nullptr) {
        if (queue != nullptr) {
            __osEnqueueThread(queue, __osRunningThread);
        }
    }
    __osDispatchThread();
}

void redispatch() {
    if (__osRunningThread != nullptr) {
        __osEnqueueThread(&__osRunQueue, __osRunningThread);
    }
    __osDispatchThread();
}

void handleRCP() {
    redispatch();
}

void initInterruptTables() {
    static const uint8_t defaultOffsets[32] = {
        0, 20, 24, 24, 28, 28, 28, 28, 32, 32, 24, 24, 28, 28, 28, 28,
        0, 4, 8, 8, 12, 12, 12, 12, 16, 16, 16, 16, 16, 16, 16, 16
    };
    std::memcpy((void*)__osIntOffTable, defaultOffsets, 32);
}

} // extern "C"
