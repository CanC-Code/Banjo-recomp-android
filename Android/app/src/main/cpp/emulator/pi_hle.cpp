#include <stdint.h>
#include <android/log.h>
#include "n64_types.h" 

extern "C" {

// Link to the recompiled OS function that sends messages
extern s32 osSendMesg(OSMesgQueue *mq, OSMesg msg, s32 flag);
extern void ResourceMgr_HandleDma(void* dramAddr, u32 devAddr, u32 size);

s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    if (direction == 0) { // OS_READ
        ResourceMgr_HandleDma(dramAddr, devAddr, size);
    }
    return 0;
}

s32 osPiStartDma(OSIoMesg *mb, s32 priority, s32 direction, 
                 u32 devAddr, void *dramAddr, u32 size, OSMesgQueue *mq) {
    
    osPiRawStartDma(direction, devAddr, dramAddr, size);

    // CRITICAL: Notify the game that DMA is finished
    if (mq != nullptr) {
        osSendMesg(mq, (OSMesg)mb, 0); // 0 = OS_MESG_NOBLOCK
    }
    return 0;
}

s32 osEPiStartDma(OSPiHandle *handle, OSIoMesg *mb, s32 direction) {
    if (mb != nullptr && direction == 0) {
        u32 devAddr    = mb->devAddr;
        void* dramAddr = mb->dramAddr;
        u32 size       = mb->size;

        ResourceMgr_HandleDma(dramAddr, devAddr, size);

        // CRITICAL: Rare games check the return queue inside the OSIoMesg header
        if (mb->hdr.retQueue != nullptr) {
            osSendMesg(mb->hdr.retQueue, mb->hdr.retMsg, 0);
        }
    }
    return 0; 
}

} // extern "C"
