#include <sched.h>
#include <map>
#include <string>
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <errno.h>

#include <android/log.h>

#include "tools/rare_decompression.h"
#include "ultra/assets_manifest.h"

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

// -----------------------------------------------------------------------
// Internal state
// -----------------------------------------------------------------------

static std::map<uint32_t, std::string> g_offsetToName;
static std::string g_assetDir;

extern "C" {

/**
 * ResourceMgr_Init
 * Now includes path normalization to handle the weird Extended Storage paths.
 */
void ResourceMgr_Init(const char* assetDir,
                      uint8_t* manifestBuf,
                      uint32_t    manifestSize) {
    if (!assetDir || assetDir[0] == '\0') {
        LOGE("Init: FAILED - assetDir is null or empty!");
        return;
    }

    g_assetDir = assetDir;
    
    // Ensure the directory ends with a slash for safe concatenation
    if (g_assetDir.back() != '/') {
        g_assetDir += "/";
    }

    g_offsetToName.clear();

    if (!manifestBuf || manifestSize < 4) {
        LOGE("Init: FAILED - manifest buffer is invalid (size: %u)", manifestSize);
        return;
    }

    uint32_t entryCount =
        (uint32_t(manifestBuf[0])      ) |
        (uint32_t(manifestBuf[1]) <<  8) |
        (uint32_t(manifestBuf[2]) << 16) |
        (uint32_t(manifestBuf[3]) << 24);

    static const uint32_t RECORD_SIZE = 144;
    uint32_t maxEntries = (manifestSize - 4) / RECORD_SIZE;
    if (entryCount > maxEntries) {
        LOGW("Manifest count mismatch (Count: %u, Max: %u). Clamping.", entryCount, maxEntries);
        entryCount = maxEntries;
    }

    const uint8_t* p = manifestBuf + 4;
    for (uint32_t i = 0; i < entryCount; ++i, p += RECORD_SIZE) {
        uint32_t romOffset =
            (uint32_t(p[0])      ) |
            (uint32_t(p[1]) <<  8) |
            (uint32_t(p[2]) << 16) |
            (uint32_t(p[3]) << 24);
            
        const char* name = reinterpret_cast<const char*>(p + 16);
        if (name[0] != '\0') {
            g_offsetToName[romOffset] = std::string(name, strnlen(name, 128));
        }
    }

    LOGI("Init: SUCCESS - Path: %s | %u assets mapped", g_assetDir.c_str(), (uint32_t)g_offsetToName.size());
}

/**
 * ResourceMgr_HandleDma
 * This intercepts the N64 game's request for data.
 */
void ResourceMgr_HandleDma(void* dramAddr,
                           uint32_t devAddr,
                           uint32_t size) {
    if (g_assetDir.empty()) {
        LOGE("DMA: FAILED - Called before Init! (Addr: 0x%08X)", devAddr);
        return;
    }
    
    if (!dramAddr || size == 0) return;

    // 1. Look up the asset name
    auto it = g_offsetToName.find(devAddr);
    if (it == g_offsetToName.end()) {
        // This is where those 0x1000/0x2000 addresses from LinkerSymbols will show up
        LOGW("DMA: Miss at 0x%08X (size %u). Check LinkerSymbols and Manifest!", devAddr, size);
        memset(dramAddr, 0, size);
        return;
    }

    // 2. Construct absolute path
    std::string filePath = g_assetDir + it->second;

    // 3. Open and Read
    FILE* f = fopen(filePath.c_str(), "rb");
    if (!f) {
        LOGE("DMA: Open FAILED! Path: %s | Error: %s", filePath.c_str(), strerror(errno));
        memset(dramAddr, 0, size);
        return;
    }

    fseek(f, 0, SEEK_END);
    long fileLen = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fileLen <= 0) {
        LOGE("DMA: File is empty: %s", filePath.c_str());
        fclose(f);
        memset(dramAddr, 0, size);
        return;
    }

    uint32_t copyLen = (uint32_t(fileLen) < size) ? uint32_t(fileLen) : size;
    size_t bytesRead = fread(dramAddr, 1, copyLen, f);
    fclose(f);

    LOGI("DMA: Loaded %zu bytes from %s to %p", bytesRead, it->second.c_str(), dramAddr);

    if (bytesRead < size) {
        memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
    }

    sched_yield();
}

} // extern "C"
