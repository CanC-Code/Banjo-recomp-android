#include <sched.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <errno.h>
#include <android/log.h>
#include <string>

#include "bka_safe_base.h"

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static std::string g_assetDir;

extern "C" {

// CRITICAL FIX: Define the ROM pointer here. It will be dynamically populated on boot.
uint8_t* gN64_ROM_Base = nullptr;

/**
 * Initializes the Resource Manager in Absolute Self-Building Mode.
 */
void ResourceMgr_Init(const char* assetDir) {
    if (!assetDir) return;

    g_assetDir = assetDir;
    if (!g_assetDir.empty() && g_assetDir.back() != '/') {
        g_assetDir += "/";
    }

    LOGI("ResourceMgr: Activated in Absolute Self-Building Mode at %s", g_assetDir.c_str());

    // Dynamically allocate and load the raw ROM so fallback DMA has real data to read
    char romPath[512];
    snprintf(romPath, sizeof(romPath), "%srom_base.bin", g_assetDir.c_str());
    FILE* f = fopen(romPath, "rb");
    
    if (f) {
        fseek(f, 0, SEEK_END);
        size_t romSize = ftell(f);
        fseek(f, 0, SEEK_SET);

        // Prevent memory leaks if the Activity restarts and re-initializes the bridge
        if (gN64_ROM_Base) {
            free(gN64_ROM_Base);
        }

        gN64_ROM_Base = static_cast<uint8_t*>(malloc(romSize));
        if (gN64_ROM_Base) {
            fread(gN64_ROM_Base, 1, romSize, f);
            LOGI("ResourceMgr: Successfully loaded rom_base.bin (%zu bytes) into contiguous memory.", romSize);
        } else {
            LOGE("ResourceMgr: FATAL - Memory allocation failed for ROM buffer.");
        }
        fclose(f);
    } else {
        LOGE("ResourceMgr: FATAL - Could not find rom_base.bin at %s", romPath);
    }
}

/**
 * Handles N64 DMA requests by intercepting decompressed targets or falling back to raw ROM.
 */
void ResourceMgr_HandleDma(void* dramAddr, uint32_t devAddr, uint32_t size) {
    // Mask off the PI domain identifier (0x10000000) to get the absolute ROM offset
    uint32_t relativeRomOffset = devAddr & 0x0FFFFFFF;

    char path[512];
    bool fileFound = false;
    FILE* f = nullptr;

    // Direct match pass
    snprintf(path, sizeof(path), "%sasset_%08X.bin", g_assetDir.c_str(), relativeRomOffset);
    f = fopen(path, "rb");

    if (!f) {
        // Safe secondary check using alternative mapping bounds 
        snprintf(path, sizeof(path), "%sasset_%08X.bin", g_assetDir.c_str(), devAddr);
        f = fopen(path, "rb");
    }

    if (f) {
        size_t bytesRead = fread(dramAddr, 1, size, f);
        fclose(f);

        // Zero-pad alignment limits required by the libultra boot microcode
        if (bytesRead < size) {
            memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
        }
        fileFound = true;
    }

    if (!fileFound) {
        if (gN64_ROM_Base != nullptr) {
            // Ensure the DMA request doesn't bleed past the 64MB virtual cartridge limit
            if (relativeRomOffset + size <= 0x04000000) {
                memcpy(dramAddr, gN64_ROM_Base + relativeRomOffset, size);
            } else {
                LOGE("DMA OOB: Attempted to read past ROM boundary at offset 0x%08X", relativeRomOffset);
                memset(dramAddr, 0, size);
            }
        } else {
            LOGE("DMA FATAL: rom_base.bin is not mapped, and asset is missing.");
            memset(dramAddr, 0, size);
        }
    }

    sched_yield();
}

} // extern "C"
