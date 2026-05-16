#include <android/log.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <sched.h>
#include <unordered_map>
#include <mutex>
#include <deque>
#include <condition_variable>

#include "n64_types.h"

// High-Level Emulation native thread tracking structures
struct NativeThread {
    pthread_t thread;
    void (*entry)(void *);
    void *arg;
    OSId id;
    OSPri pri;
};

// High-Level Emulation message queue structures
struct NativeQueue {
    std::deque<OSMesg> buffer;
    int capacity;
    std::mutex mtx;
    std::condition_variable cv_recv;
    std::condition_variable cv_send;
};

// Registries to map raw N64 OS pointers to native Android POSIX/C++ structures
static std::unordered_map<OSThread*, NativeThread*> s_threadRegistry;
static std::mutex s_threadMutex;

static std::unordered_map<OSMesgQueue*, NativeQueue*> s_queueRegistry;
static std::mutex s_queueMutex;

extern "C" {
// Recompiled OS headers
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>

#define LOG_TAG "BKA_STUBS"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

/* ============================================================
   1. OS GLOBALS & LINKER FIXES
   ============================================================ */

static OSPiHandle sPiTablePool[2];
OSPiHandle* __osPiTable = sPiTablePool;

void* __osViNext = nullptr; 
void* __osViCurr = nullptr;
OSDevMgr __osPiDevMgr;

// Dummy state table for internal libultra interrupt handlers (leointerrupt.c)
u32 __osEventStateTab[16];

void osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    LOGI("BKA-HLE: osCreatePiManager initialized.");
}

void __osViInit(void) {
    LOGI("BKA-HLE: __osViInit executed.");
}

/* ============================================================
   2. HLE NATIVE THREADING (POSIX Pthreads)
   Intercepts MIPS hardware context switches and routes to POSIX.
   ============================================================ */

void osCreateThread(OSThread *t, OSId id, void (*entry)(void *), void *arg, void *sp, OSPri p) {
    std::lock_guard<std::mutex> lock(s_threadMutex);
    
    t->id = id;
    t->priority = p;
    
    NativeThread* nt = new NativeThread();
    nt->entry = entry;
    nt->arg = arg;
    nt->id = id;
    nt->pri = p;
    nt->thread = 0;
    
    s_threadRegistry[t] = nt;
    LOGI("BKA-HLE: osCreateThread mapped POSIX Thread ID %d", id);
}

static void* NativeThreadWrapper(void* arg) {
    NativeThread* nt = static_cast<NativeThread*>(arg);
    LOGI("BKA-HLE: Native Thread ID %d starting execution.", nt->id);
    
    // Execute the recompiled N64 thread function
    nt->entry(nt->arg);
    
    LOGI("BKA-HLE: Native Thread ID %d terminated cleanly.", nt->id);
    return nullptr;
}

void osStartThread(OSThread *t) {
    std::lock_guard<std::mutex> lock(s_threadMutex);
    
    // Sometimes the N64 passes NULL to start the idle thread, but in recompiled ports
    // we explicitly track and boot the passed thread structure.
    if (t != nullptr && s_threadRegistry.find(t) != s_threadRegistry.end()) {
        NativeThread* nt = s_threadRegistry[t];
        pthread_create(&nt->thread, nullptr, NativeThreadWrapper, nt);
        
        // Detach so the Android kernel can automatically clean up resources when the thread finishes
        pthread_detach(nt->thread);
        LOGI("BKA-HLE: osStartThread launched Thread ID %d", nt->id);
    }
}

void osStopThread(OSThread *t) {
    // N64 uses this to kill threads. True POSIX pthread_cancel is unsafe for C++ memory.
    // For HLE, we let the thread function hit its natural exit or blocking condition.
    LOGW("BKA-HLE: osStopThread intercepted. Letting thread wind down natively.");
}

void osDestroyThread(OSThread *t) {
    std::lock_guard<std::mutex> lock(s_threadMutex);
    if (s_threadRegistry.find(t) != s_threadRegistry.end()) {
        delete s_threadRegistry[t];
        s_threadRegistry.erase(t);
        LOGI("BKA-HLE: osDestroyThread cleaned up resources.");
    }
}

void osYieldThread(void) {
    // Relinquish CPU time back to the Android scheduler
    sched_yield();
}

void osSetThreadPri(OSThread *t, OSPri pri) {
    if (t) t->priority = pri;
}

OSPri osGetThreadPri(OSThread *t) {
    return t ? t->priority : 0;
}

void __osDequeueThread(OSThread **queue, OSThread *t) {
    // Internal libultra linked-list stub used by settreadpri.c
    // HLE threading bypasses the raw software scheduler.
}

/* ============================================================
   3. HLE MESSAGE QUEUE (Anti-Deadlock)
   Fully synchronized C++ condition variables to manage N64 IPC.
   ============================================================ */

void osCreateMesgQueue(OSMesgQueue *mq, OSMesg *msgBuf, s32 count) {
    // Keep the N64 struct updated for internal engine checks
    mq->validCount = 0;
    mq->first = 0;
    mq->msgCount = count;
    mq->msg = msgBuf;

    std::lock_guard<std::mutex> lock(s_queueMutex);
    if (s_queueRegistry.find(mq) != s_queueRegistry.end()) {
        delete s_queueRegistry[mq];
    }
    
    NativeQueue* nq = new NativeQueue();
    nq->capacity = count;
    s_queueRegistry[mq] = nq;
    LOGI("BKA-HLE: osCreateMesgQueue registered queue with capacity %d", count);
}

void osSetEventMesg(OSEvent e, OSMesgQueue *mq, OSMesg msg) {
    // Hooks hardware events (like VI VBlank or DMA complete) to specific queues
    LOGI("BKA-HLE: osSetEventMesg bound event %d", (int)e);
}

s32 osSendMesg(OSMesgQueue *mq, OSMesg msg, s32 flag) {
    NativeQueue* nq = nullptr;
    {
        std::lock_guard<std::mutex> lock(s_queueMutex);
        auto it = s_queueRegistry.find(mq);
        if (it == s_queueRegistry.end()) return -1;
        nq = it->second;
    }

    std::unique_lock<std::mutex> lock(nq->mtx);
    if (flag == OS_MESG_BLOCK) {
        nq->cv_send.wait(lock, [nq]() { return nq->buffer.size() < nq->capacity; });
    } else {
        if (nq->buffer.size() >= nq->capacity) return -1;
    }

    nq->buffer.push_back(msg);
    mq->validCount = nq->buffer.size(); // Keep struct semi-accurate for raw reads
    nq->cv_recv.notify_one();
    
    return 0;
}

s32 osJamMesg(OSMesgQueue *mq, OSMesg msg, s32 flag) {
    NativeQueue* nq = nullptr;
    {
        std::lock_guard<std::mutex> lock(s_queueMutex);
        auto it = s_queueRegistry.find(mq);
        if (it == s_queueRegistry.end()) return -1;
        nq = it->second;
    }

    std::unique_lock<std::mutex> lock(nq->mtx);
    if (flag == OS_MESG_BLOCK) {
        nq->cv_send.wait(lock, [nq]() { return nq->buffer.size() < nq->capacity; });
    } else {
        if (nq->buffer.size() >= nq->capacity) return -1;
    }

    // Jamming pushes the message to the absolute front of the line
    nq->buffer.push_front(msg);
    mq->validCount = nq->buffer.size();
    nq->cv_recv.notify_one();
    
    return 0;
}

s32 osRecvMesg(OSMesgQueue *mq, OSMesg *msg, s32 flag) {
    NativeQueue* nq = nullptr;
    {
        std::lock_guard<std::mutex> lock(s_queueMutex);
        auto it = s_queueRegistry.find(mq);
        if (it == s_queueRegistry.end()) return -1;
        nq = it->second;
    }

    std::unique_lock<std::mutex> lock(nq->mtx);
    if (flag == OS_MESG_BLOCK) {
        nq->cv_recv.wait(lock, [nq]() { return !nq->buffer.empty(); });
    } else {
        if (nq->buffer.empty()) return -1;
    }

    if (msg != nullptr) {
        *msg = nq->buffer.front();
    }
    nq->buffer.pop_front();
    mq->validCount = nq->buffer.size();
    nq->cv_send.notify_one();
    
    return 0;
}

/* ============================================================
   4. HLE DMA REDIRECTION
   ============================================================ */

extern s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size);
s32 osEPiRawStartDma(OSPiHandle *handle, s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

/* ============================================================
   5. GAME ENTRY POINTS & ENGINE DRIVER
   ============================================================ */

extern void func_80000450(int32_t arg0); 
AndroidBridgeGlobals* gBridgeGlobals = nullptr;

void core1_reset(void) {
    LOGI("BKA-CORE: System Reset.");
}

void core1_stepCPU(void) {
    static bool engine_ignited = false;
    if (!engine_ignited) {
        LOGI("BKA-STUBS: >>> IGNITING ENGINE (func_80000450) <<<");
        engine_ignited = true;
        func_80000450(0); 
    }
}

void mainLoop(void) {
    LOGI("BKA-STUBS: mainLoop starting.");
    core1_reset();

    static const uint32_t TARGET_FRAME_US = 33333u; 
    uint32_t frameCount = 0;

    while (true) {
        struct timespec ts_start, ts_end;
        clock_gettime(CLOCK_MONOTONIC, &ts_start);

        core1_stepCPU();    

        if (gBridgeGlobals != nullptr) {
            gBridgeGlobals->frameCount++;
        }

        clock_gettime(CLOCK_MONOTONIC, &ts_end);
        uint32_t elapsed_us = (uint32_t)(
            (uint64_t)(ts_end.tv_sec  - ts_start.tv_sec)  * 1000000u +
            (uint64_t)(ts_end.tv_nsec - ts_start.tv_nsec) / 1000u
        );

        if (elapsed_us < TARGET_FRAME_US) {
            usleep(TARGET_FRAME_US - elapsed_us);
        }

        if ((++frameCount % 300) == 0) {
            LOGI("BKA-STUBS: %u frames processed", frameCount);
        }
    }
}

/* ============================================================
   6. MISC FALLBACKS
   ============================================================ */

void core1_loadOTR(uint8_t* data, size_t size) {}
int  func_80258A4C(void) { return 0; }
void func_8025A123(void) {}
void initInterruptTables(void) {}

} // extern "C"
