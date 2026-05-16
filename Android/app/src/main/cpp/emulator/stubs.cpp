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

// -------------------------------------------------------------------------
// HIGH-LEVEL EMULATION NATIVE STRUCTURES
// -------------------------------------------------------------------------
struct NativeThread {
    pthread_t thread;
    void (*entry)(void *);
    void *arg;
    OSId id;
    OSPri pri;
};

struct NativeQueue {
    std::deque<OSMesg> buffer;
    int capacity;
    std::mutex mtx;
    std::condition_variable cv_recv;
    std::condition_variable cv_send;
};

struct EventRoute {
    OSMesgQueue* mq;
    OSMesg msg;
};

// -------------------------------------------------------------------------
// REGISTRIES & SYNCHRONIZATION (THE GIL)
// -------------------------------------------------------------------------
// The N64 Global Interpreter Lock (GIL). 
// Enforces single-core execution on a multi-core Android processor.
static std::recursive_mutex s_n64_gil;

static std::unordered_map<OSThread*, NativeThread*> s_threadRegistry;
static std::mutex s_threadMutex;

static std::unordered_map<OSMesgQueue*, NativeQueue*> s_queueRegistry;
static std::mutex s_queueMutex;

static std::unordered_map<int, EventRoute> s_eventRegistry;
static std::mutex s_eventMutex;

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
u32 __osEventStateTab[16];

void osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    LOGI("BKA-HLE: osCreatePiManager initialized.");
}

void __osViInit(void) {
    LOGI("BKA-HLE: __osViInit executed.");
}

/* ============================================================
   2. HLE NATIVE THREADING WITH GIL
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
}

static void* NativeThreadWrapper(void* arg) {
    NativeThread* nt = static_cast<NativeThread*>(arg);
    LOGI("BKA-HLE: Native Thread ID %d starting execution.", nt->id);
    
    // Acquire the N64 CPU Lock. Only ONE thread runs N64 logic at a time.
    s_n64_gil.lock();
    nt->entry(nt->arg);
    s_n64_gil.unlock();
    
    LOGI("BKA-HLE: Native Thread ID %d terminated cleanly.", nt->id);
    return nullptr;
}

void osStartThread(OSThread *t) {
    std::lock_guard<std::mutex> lock(s_threadMutex);
    if (t != nullptr && s_threadRegistry.find(t) != s_threadRegistry.end()) {
        NativeThread* nt = s_threadRegistry[t];
        pthread_create(&nt->thread, nullptr, NativeThreadWrapper, nt);
        pthread_detach(nt->thread);
    }
}

void osStopThread(OSThread *t) {
    LOGW("BKA-HLE: osStopThread intercepted. Letting thread wind down natively.");
}

void osDestroyThread(OSThread *t) {
    std::lock_guard<std::mutex> lock(s_threadMutex);
    if (s_threadRegistry.find(t) != s_threadRegistry.end()) {
        delete s_threadRegistry[t];
        s_threadRegistry.erase(t);
    }
}

void osYieldThread(void) {
    // Release the N64 CPU lock, yield Android CPU time, and re-acquire.
    s_n64_gil.unlock();
    sched_yield();
    s_n64_gil.lock();
}

void osSetThreadPri(OSThread *t, OSPri pri) { if (t) t->priority = pri; }
OSPri osGetThreadPri(OSThread *t) { return t ? t->priority : 0; }
void __osDequeueThread(OSThread **queue, OSThread *t) {}

/* ============================================================
   3. EVENT ROUTING & MESSAGE QUEUES
   ============================================================ */

void osCreateMesgQueue(OSMesgQueue *mq, OSMesg *msgBuf, s32 count) {
    mq->validCount = 0;
    mq->first = 0;
    mq->msgCount = count;
    mq->msg = msgBuf;

    std::lock_guard<std::mutex> lock(s_queueMutex);
    if (s_queueRegistry.find(mq) != s_queueRegistry.end()) delete s_queueRegistry[mq];
    
    NativeQueue* nq = new NativeQueue();
    nq->capacity = count;
    s_queueRegistry[mq] = nq;
}

void osSetEventMesg(OSEvent e, OSMesgQueue *mq, OSMesg msg) {
    std::lock_guard<std::mutex> lock(s_eventMutex);
    s_eventRegistry[(int)e] = {mq, msg};
    LOGI("BKA-HLE: Bound hardware event %d to queue", (int)e);
}

// Global Trigger to be called by Android Native Bridge (e.g., Virtual VBlank)
void HLE_TriggerN64Event(int event_id) {
    std::lock_guard<std::mutex> lock(s_eventMutex);
    if (s_eventRegistry.count(event_id)) {
        EventRoute route = s_eventRegistry[event_id];
        osSendMesg(route.mq, route.msg, OS_MESG_NOBLOCK);
    }
}

s32 osSendMesg(OSMesgQueue *mq, OSMesg msg, s32 flag) {
    NativeQueue* nq = nullptr;
    {
        std::lock_guard<std::mutex> lock(s_queueMutex);
        if (s_queueRegistry.find(mq) == s_queueRegistry.end()) return -1;
        nq = s_queueRegistry[mq];
    }

    std::unique_lock<std::mutex> lock(nq->mtx);
    if (flag == OS_MESG_BLOCK) {
        // Yield the GIL so other threads can process while we sleep
        s_n64_gil.unlock();
        nq->cv_send.wait(lock, [nq]() { return nq->buffer.size() < nq->capacity; });
        s_n64_gil.lock();
    } else {
        if (nq->buffer.size() >= nq->capacity) return -1;
    }

    nq->buffer.push_back(msg);
    mq->validCount = nq->buffer.size();
    nq->cv_recv.notify_one();
    return 0;
}

s32 osJamMesg(OSMesgQueue *mq, OSMesg msg, s32 flag) {
    NativeQueue* nq = nullptr;
    {
        std::lock_guard<std::mutex> lock(s_queueMutex);
        if (s_queueRegistry.find(mq) == s_queueRegistry.end()) return -1;
        nq = s_queueRegistry[mq];
    }

    std::unique_lock<std::mutex> lock(nq->mtx);
    if (flag == OS_MESG_BLOCK) {
        s_n64_gil.unlock();
        nq->cv_send.wait(lock, [nq]() { return nq->buffer.size() < nq->capacity; });
        s_n64_gil.lock();
    } else {
        if (nq->buffer.size() >= nq->capacity) return -1;
    }

    nq->buffer.push_front(msg); // Jam to front
    mq->validCount = nq->buffer.size();
    nq->cv_recv.notify_one();
    return 0;
}

s32 osRecvMesg(OSMesgQueue *mq, OSMesg *msg, s32 flag) {
    NativeQueue* nq = nullptr;
    {
        std::lock_guard<std::mutex> lock(s_queueMutex);
        if (s_queueRegistry.find(mq) == s_queueRegistry.end()) return -1;
        nq = s_queueRegistry[mq];
    }

    std::unique_lock<std::mutex> lock(nq->mtx);
    if (flag == OS_MESG_BLOCK) {
        s_n64_gil.unlock();
        nq->cv_recv.wait(lock, [nq]() { return !nq->buffer.empty(); });
        s_n64_gil.lock();
    } else {
        if (nq->buffer.empty()) return -1;
    }

    if (msg != nullptr) *msg = nq->buffer.front();
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

void core1_reset(void) { LOGI("BKA-CORE: System Reset."); }

void core1_stepCPU(void) {
    static bool engine_ignited = false;
    if (!engine_ignited) {
        LOGI("BKA-STUBS: >>> IGNITING ENGINE (func_80000450) <<<");
        engine_ignited = true;
        
        s_n64_gil.lock();
        func_80000450(0); 
        s_n64_gil.unlock();
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
        if (gBridgeGlobals != nullptr) gBridgeGlobals->frameCount++;

        clock_gettime(CLOCK_MONOTONIC, &ts_end);
        uint32_t elapsed_us = (uint32_t)((uint64_t)(ts_end.tv_sec - ts_start.tv_sec) * 1000000u + (uint64_t)(ts_end.tv_nsec - ts_start.tv_nsec) / 1000u);

        if (elapsed_us < TARGET_FRAME_US) usleep(TARGET_FRAME_US - elapsed_us);
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
