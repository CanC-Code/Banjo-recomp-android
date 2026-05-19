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
    // CRITICAL CORRECTION: Map using raw addresses first before stripping bits
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
        // CRITICAL CORRECTION: Clean physical range tracking configuration fallback.
        // Strip out the base index boundary mask prior to pushing through the address macro translator.
        uintptr_t cleanRomOffset = (uintptr_t)(devAddr & 0x03FFFFFF);
        uintptr_t host_dev = BKA_TRANSLATE_ADDR(cleanRomOffset);
        
        if (host_dev) {
            memcpy(dramAddr, reinterpret_cast<void*>(host_dev), size);
        } else {
            LOGE("DMA FATAL: Asset at absolute address 0x%08X (offset: 0x%08X) missing from storage and memory mapping bounds failed.", devAddr, relativeRomOffset);
            memset(dramAddr, 0, size);
        }
    }

    sched_yield();
}

} // extern "C"
