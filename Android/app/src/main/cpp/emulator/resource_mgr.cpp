#include <sched.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <errno.h>
#include <android/log.h>
#include <string>

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static std::string g_assetDir;

extern "C" {

// Access the host physical mapper from bka_safe_base.h
extern uintptr_t BKA_TRANSLATE_ADDR(uintptr_t addr);

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
    // Strip the physical cart domain indicator (0x10) to isolate the raw ROM offset
    uint32_t romOffset = devAddr & 0x0FFFFFFF;
    
    char path[512];
    snprintf(path, sizeof(path), "%sasset_%08X.bin", g_assetDir.c_str(), romOffset);

    FILE* f = fopen(path, "rb");
    if (f) {
        size_t bytesRead = fread(dramAddr, 1, size, f);
        fclose(f);
        
        // Zero-pad alignment limits required by the libultra boot microcode
        if (bytesRead < size) {
            memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
        }
    } else {
        // Fallback directly to the RAW ROM mapped memory stream for uncompressed assets
        uintptr_t host_dev = BKA_TRANSLATE_ADDR((uintptr_t)devAddr);
        if (host_dev) {
            memcpy(dramAddr, reinterpret_cast<void*>(host_dev), size);
        } else {
            LOGE("DMA FATAL: Asset 0x%08X missing from disk and memory mapping bounds failed.", devAddr);
            memset(dramAddr, 0, size);
        }
    }
    
    sched_yield();
}

} // extern "C"
