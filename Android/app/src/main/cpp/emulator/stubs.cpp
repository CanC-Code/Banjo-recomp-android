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
#include "bka_safe_base.h" 

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
static std::recursive_mutex s_n64_gil;

static std::unordered_map<OSThread*, NativeThread*> s_threadRegistry;
static std::mutex s_threadMutex;

static std::unordered_map<OSMesgQueue*, NativeQueue*> s_queueRegistry;
static std::mutex s_queueMutex;

static std::unordered_map<int, EventRoute> s_eventRegistry;
static std::mutex s_eventMutex;

// PI Manager Subsystem Tracking
static OSMesgQueue* s_hlePiCmdQueue = nullptr;
static pthread_t    s_hlePiMgrThread;

extern "C" {
// Recompiled OS headers
#include <PR/os_pi.h>
#include <PR/os_thread.h>
#include <PR/os_message.h>
#include <PR/sptask.h>  
#include <PR/os_ai.h>      

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
    LOGW("BKA-HLE: osStopThread intercepted.");
}

void osDestroyThread(OSThread *t) {
    std::lock_guard<std::mutex> lock(s_threadMutex);
    if (s_threadRegistry.find(t) != s_threadRegistry.end()) {
        delete s_threadRegistry[t];
        s_threadRegistry.erase(t);
    }
}

void osYieldThread(void) {
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

    nq->buffer.push_front(msg); 
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
   4. HLE DMA REDIRECTION & AUTOMATED PI MANAGER
   ============================================================ */

s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    if (size == 0) return 0;

    uintptr_t host_dram = BKA_TRANSLATE_ADDR((uintptr_t)dramAddr);
    uintptr_t host_dev  = BKA_TRANSLATE_ADDR((uintptr_t)devAddr);

    if (!host_dram || !host_dev) return -1;

    void* src_ptr = (direction == OS_READ) ? reinterpret_cast<void*>(host_dev) : reinterpret_cast<void*>(host_dram);
    void* dest_ptr = (direction == OS_READ) ? reinterpret_cast<void*>(host_dram) : reinterpret_cast<void*>(host_dev);

    uint8_t* ram_base = __atomic_load_n(&gN64_RDRAM, __ATOMIC_ACQUIRE);
    if (dest_ptr >= ram_base && dest_ptr < (ram_base + BKA_RDRAM_ALLOC_SIZE)) {
        size_t space_remaining = (ram_base + BKA_RDRAM_ALLOC_SIZE) - reinterpret_cast<uint8_t*>(dest_ptr);
        if (size > space_remaining) size = space_remaining;
    }

    memcpy(dest_ptr, src_ptr, size);
    return 0;
}

s32 osEPiRawStartDma(OSPiHandle *handle, s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

static void* HLE_PiManagerWorker(void* arg) {
    LOGI("BKA-HLE: Peripheral Interface (PI) Async Manager Thread Engaged.");
    s_n64_gil.lock();
    
    while (true) {
        OSMesg msg = nullptr;
        s32 ret = osRecvMesg(s_hlePiCmdQueue, &msg, OS_MESG_BLOCK);
        if (ret != 0 || msg == nullptr) continue;

        OSIoMesg* ioMsg = reinterpret_cast<OSIoMesg*>(msg);
        osPiRawStartDma(ioMsg->hdr.type, ioMsg->devAddr, ioMsg->dramAddr, ioMsg->size);

        if (ioMsg->hdr.retQueue != nullptr) {
            osSendMesg(ioMsg->hdr.retQueue, reinterpret_cast<OSMesg>(ioMsg), OS_MESG_NOBLOCK);
        }
    }
    
    s_n64_gil.unlock();
    return nullptr;
}

void osCreatePiManager(OSPri pri, OSMesgQueue *cmdQ, OSMesg *cmdBuf, s32 cmdMsgCnt) {
    s_hlePiCmdQueue = cmdQ;
    
    pthread_create(&s_hlePiMgrThread, nullptr, HLE_PiManagerWorker, nullptr);
    pthread_detach(s_hlePiMgrThread);
    LOGI("BKA-HLE: osCreatePiManager successfully generated background processing engine.");
}

/* ============================================================
   5. SAFE AUDIO/VIDEO ENDPOINTS (DROP LOGIC)
   ============================================================ */

void osSpTaskLoad(OSTask *tp) {}

void osSpTaskStartGo(OSTask *tp) {
    if (tp == nullptr) return;
    if (tp->t.type == M_GFXTASK) {
        HLE_TriggerN64Event(1); // OS_EVENT_SP
        HLE_TriggerN64Event(3); // OS_EVENT_DP
    } 
    else if (tp->t.type == M_AUDTASK) {
        HLE_TriggerN64Event(1); // OS_EVENT_SP
    }
}

void osSpTaskYield(void) {}
OSYieldResult osSpTaskYielded(OSTask *tp) { return (OSYieldResult)0; }

s32 osAiSetNextBuffer(void *bufPtr, u32 size) {
    if (size == 0 || bufPtr == nullptr) return 0;
    HLE_TriggerN64Event(9); // OS_EVENT_AI
    return 0;
}

u32 osAiGetLength(void) { return 0; }
s32 osAiSetFrequency(u32 frequency) { return 0; }

/* ============================================================
   6. SECURE ENGINE IGNITION & LOCK MANIPULATION
   ============================================================ */

extern void func_80000450(int32_t arg0); 

void BKA_StartEngine(void) {
    LOGI("BKA-STUBS: >>> SECURE CONCURRENT IGNITION VIA GIL LOCK <<<");
    s_n64_gil.lock();
    func_80000450(0);
    s_n64_gil.unlock();
}

// Thread context bridge hooks used by NativeBridge to cycle execution constraints
void BKA_DropEngineLock(void) {
    s_n64_gil.unlock();
}

void BKA_ClaimEngineLock(void) {
    s_n64_gil.lock();
}

void mainLoop(void) {}
void core1_loadOTR(uint8_t* data, size_t size) {}
int  func_80258A4C(void) { return 0; }
void func_8025A123(void) {}
void initInterruptTables(void) {}

} // extern "C"
