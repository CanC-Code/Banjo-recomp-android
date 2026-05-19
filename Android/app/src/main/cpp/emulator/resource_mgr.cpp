#include <sched.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <errno.h>
#include <android/log.h>
#include <string>

// Correctly include the macro and inline functions for memory translation
#include "bka_safe_base.h"

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static std::string g_assetDir;

extern "C" {

// CRITICAL FIX: Import the global ROM pointer established by lowlevel_bridge.cpp
extern uint8_t* gN64_ROM_Base;

/**
 * Initializes the Resource Manager in Absolute Self-Building Mode.
 * No static manifest mapping arrays are required.
 */
void ResourceMgr_Init(const char* assetDir) {
    if (!assetDir) return;

    g_assetDir = assetDir;
    if (!g_assetDir.empty() && g_assetDir.back() != '/') {
        g_assetDir += "/";
    }

    LOGI("ResourceMgr: Activated in Absolute Self-Building Mode at %s", g_assetDir.c_str());
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

    // Direct match pass (Standard absolute tracking alignment used by extractor)
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
        // CRITICAL CORRECTION: Bypass BKA_TRANSLATE_ADDR for Cartridge reads.
        // bka_safe_base maps low addresses to RDRAM. We must pull directly from the ROM pool.
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
