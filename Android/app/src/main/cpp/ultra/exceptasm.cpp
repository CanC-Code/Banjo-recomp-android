#include <cstdint>
#include <cstring>
#include "n64_types.h" // Structures are now inherited from here

extern "C" {

// Global Scheduler Symbols (Keep these exported for the game to find)
OSThread* __osRunningThread = nullptr;
OSThread* __osRunQueue = nullptr;
OSThread* __osFaultedThread = nullptr;
CPUState __osThreadSave; 

volatile uint32_t __OSGlobalIntMask = 0xFFFFFFFF;
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
    
    // N64 logic: Status register bit 0 is the global interrupt enable (IE)
    // We simulate "enabling interrupts" when a thread starts.
    __osRunningThread->context.status |= 0x0001; 
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
    // Logic: In an Android port, this is triggered by the Graphics/Audio loop
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
