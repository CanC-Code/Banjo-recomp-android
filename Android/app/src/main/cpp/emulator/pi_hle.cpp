#include <stdint.h>
#include <android/log.h>
#include "n64_types.h" 

extern "C" {

// Link to the recompiled OS function that handles thread messaging
extern s32 osSendMesg(OSMesgQueue *mq, OSMesg msg, s32 flag);
extern void ResourceMgr_HandleDma(void* dramAddr, u32 devAddr, u32 size);

/**
 * Basic Raw DMA (Synchronous)
 */
s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    if (direction == 0) { // OS_READ
        ResourceMgr_HandleDma(dramAddr, devAddr, size);
    }
    return 0;
}

/**
 * Standard PI DMA
 * Uses the explicit message queue passed by the game.
 */
s32 osPiStartDma(OSIoMesg *mb, s32 priority, s32 direction, 
                 u32 devAddr, void *dramAddr, u32 size, OSMesgQueue *mq) {
    
    osPiRawStartDma(direction, devAddr, dramAddr, size);

    // Notify the game thread that data is ready
    if (mq != nullptr) {
        osSendMesg(mq, (OSMesg)mb, 0); // Send the block as the message
    }
    return 0;
}

/**
 * Extended PI DMA (Used by Banjo-Kazooie)
 * Accesses the internal header to find the return queue.
 */
s32 osEPiStartDma(OSPiHandle *handle, OSIoMesg *mb, s32 direction) {
    if (mb != nullptr && direction == 0) {
        u32 devAddr    = mb->devAddr;
        void* dramAddr = mb->dramAddr;
        u32 size       = mb->size;

        // Perform the actual data copy from assets to RAM
        ResourceMgr_HandleDma(dramAddr, devAddr, size);

        // Notify the return queue if one was provided in the header
        if (mb->hdr.retQueue != nullptr) {
            // We send the pointer to the message block (mb) as the signal.
            // This is how the recompiled game logic knows WHICH DMA finished.
            osSendMesg(mb->hdr.retQueue, (OSMesg)mb, 0);
        }
    }
    return 0; 
}

} // extern "C"
