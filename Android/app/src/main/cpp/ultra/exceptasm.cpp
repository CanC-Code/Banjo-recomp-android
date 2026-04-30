#include <cstdint>
#include <cstring>
#include "n64_types.h" // CPUState and OSThread should be defined here

// Usually, OSIntMask is defined in PR/os_system.h as an unsigned int.
// We include the header or use the exact type to prevent redefinition errors.
#include <PR/os_internal.h> 

extern "C" {

// Global Scheduler Symbols
OSThread* __osRunningThread = nullptr;
OSThread* __osRunQueue = nullptr;
OSThread* __osFaultedThread = nullptr;

// 1. CPUState is now recognized because it's in n64_types.h
CPUState __osThreadSave; 

// 2. FIX: Use OSIntMask to match the declaration in os_system.h
// The SDK defines this as: extern OSIntMask __OSGlobalIntMask;
OSIntMask __OSGlobalIntMask = 0xFFFFFFFF;

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

    // 3. FIX: Take the address of the context before casting.
    // __osRunningThread->context is the struct/array itself. 
    // We need its memory address (&) to cast it to a uint32_t pointer.
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

// The RCP handler maps hardware signals (VI, SP, DP) to software events
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
