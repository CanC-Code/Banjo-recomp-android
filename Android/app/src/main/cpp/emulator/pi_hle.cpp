#include <stdint.h>
#include <android/log.h>

extern "C" {

// Logic from resource_mgr.cpp
extern void ResourceMgr_HandleDma(void* dramAddr, uint32_t devAddr, uint32_t size);

// Low level PI Raw DMA - Used in boot
int32_t osPiRawStartDma(int32_t direction, uint32_t devAddr, void *dramAddr, uint32_t size) {
    // 0 = OS_READ (Cartridge to RAM)
    if (direction == 0) {
        ResourceMgr_HandleDma(dramAddr, devAddr, size);
    }
    return 0;
}

// High level PI DMA - Used by game threads
int32_t osPiStartDma(void* mb, int32_t priority, int32_t direction, 
                     uint32_t devAddr, void *dramAddr, uint32_t size, void* mq) {
    return osPiRawStartDma(direction, devAddr, dramAddr, size);
}

// Rareware often uses a custom EPi (Extended PI) call as well
int32_t osEPiStartDma(void* handle, void* mb, int32_t direction) {
    // Extracting fields from OSIoMesg (mb) would go here
    return 0; 
}

}
