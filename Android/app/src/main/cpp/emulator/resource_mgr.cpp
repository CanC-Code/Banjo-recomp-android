#include <sched.h>
#include <map>
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <errno.h>
#include <android/log.h>

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

static std::map<uint32_t, std::string> g_offsetToName;
static std::string g_assetDir;

extern "C" {

/**
 * Initializes the Resource Manager by reading the self-built asset index.
 * Requires NO static manifest buffer, fulfilling the "absolutely self-building" mandate.
 * @param assetDir The directory where .bin files and assets.idx were extracted.
 */
void ResourceMgr_Init(const char* assetDir) {
    if (!assetDir) {
        LOGE("FATAL: ResourceMgr_Init received an invalid asset directory path.");
        return;
    }

    g_assetDir = assetDir;
    if (!g_assetDir.empty() && g_assetDir.back() != '/') {
        g_assetDir += "/";
    }

    g_offsetToName.clear();

    std::string idxPath = g_assetDir + "assets.idx";
    FILE* f = fopen(idxPath.c_str(), "rb");
    if (!f) {
        // Enforce a hard failure warning. A missing registry will cause the PI manager to starve.
        LOGE("FATAL: assets.idx not found at %s. The OTR pipeline failed to generate the asset map.", idxPath.c_str());
        return;
    }

    // Parse the dynamically generated binary map
    while (true) {
        uint32_t offset;
        if (fread(&offset, 4, 1, f) != 1) break;
        
        uint8_t len;
        if (fread(&len, 1, 1, f) != 1) break;
        
        char name[256];
        if (fread(name, 1, len, f) != 1) break;
        name[len] = '\0';
        
        g_offsetToName[offset] = std::string(name);
    }
    fclose(f);

    LOGI("ResourceMgr: Successfully self-built map of %zu assets from %s", g_offsetToName.size(), assetDir);
}

/**
 * Handles N64 DMA requests by loading the corresponding extracted .bin file into DRAM.
 * @param dramAddr The destination address in the N64's emulated RAM
 * @param devAddr The source address (ROM offset) requested by the game
 * @param size The number of bytes to transfer
 */
void ResourceMgr_HandleDma(void* dramAddr, uint32_t devAddr, uint32_t size) {
    auto it = g_offsetToName.find(devAddr);

    if (it == g_offsetToName.end()) {
        LOGE("DMA Fail: No asset found at ROM offset 0x%08X. Filling DRAM with 0.", devAddr);
        memset(dramAddr, 0, size);
        return;
    }

    std::string fullPath = g_assetDir + it->second;

    FILE* f = fopen(fullPath.c_str(), "rb");
    if (!f) {
        LOGE("DMA Fail: Cannot open file %s (Error: %s)", fullPath.c_str(), strerror(errno));
        memset(dramAddr, 0, size);
        return;
    }

    size_t bytesRead = fread(dramAddr, 1, size, f);
    fclose(f);

    if (bytesRead < size) {
        memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
        LOGW("DMA Warning: File %s was smaller than requested size %u.", it->second.c_str(), size);
    }

    LOGI("DMA Success: Loaded %s (Offset: 0x%08X, Size: %u)", it->second.c_str(), devAddr, size);
    sched_yield();
}

} // extern "C"
