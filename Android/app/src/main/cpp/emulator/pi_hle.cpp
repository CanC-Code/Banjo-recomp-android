#include <stdint.h>
#include <android/log.h>
#include "n64_types.h" // Includes ultra64.h and the correct types

extern "C" {

// Logic from resource_mgr.cpp
extern void ResourceMgr_HandleDma(void* dramAddr, u32 devAddr, u32 size);

/**
 * Low level PI Raw DMA
 * Used during boot and simple synchronous transfers.
 */
s32 osPiRawStartDma(s32 direction, u32 devAddr, void *dramAddr, u32 size) {
    // direction: 0 = OS_READ (Cartridge -> RAM), 1 = OS_WRITE
    if (direction == 0) {
        // High-Level Emulation: Redirect the request to our resource manager
        ResourceMgr_HandleDma(dramAddr, devAddr, size);
    }
    return 0;
}

/**
 * High level PI DMA
 * Used by game threads. Matches the declaration in PR/os_pi.h
 */
s32 osPiStartDma(OSIoMesg *mb, s32 priority, s32 direction, 
                 u32 devAddr, void *dramAddr, u32 size, OSMesgQueue *mq) {
    // Simply pass the explicit parameters to the raw handler
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

/**
 * Extended PI Start DMA
 * Rareware games use this for most of their asset loading.
 * Unlike standard DMA, the addresses and size are stored inside the OSIoMesg struct.
 */
s32 osEPiStartDma(OSPiHandle *handle, OSIoMesg *mb, s32 direction) {
    if (mb != nullptr && direction == 0) {
        // Extract DMA parameters from the N64 IO Message structure
        u32 devAddr   = mb->devAddr;
        void* dramAddr = mb->dramAddr;
        u32 size      = mb->size;

        ResourceMgr_HandleDma(dramAddr, devAddr, size);
    }
    return 0; 
}

} // extern "C"
