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

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

// -----------------------------------------------------------------------
// Internal state
// -----------------------------------------------------------------------

// Maps a ROM-address offset -> asset name (from the manifest)
static std::map<uint32_t, std::string> g_offsetToName;
static std::string g_assetDir;

// Helper to read 32-bit integers safely (matches your builder logic)
static uint32_t read_u32_le(const uint8_t* ptr) {
    return (uint32_t(ptr[0])      ) |
           (uint32_t(ptr[1]) <<  8) |
           (uint32_t(ptr[2]) << 16) |
           (uint32_t(ptr[3]) << 24);
}

extern "C" {

/**
 * ResourceMgr_Init
 * Synchronized with otr_builder.cpp (48-byte record stride)
 */
void ResourceMgr_Init(const char* assetDir,
                      uint8_t* manifestBuf,
                      uint32_t    manifestSize) {
    if (!assetDir || assetDir[0] == '\0') {
        LOGE("Init: FAILED - assetDir is null or empty");
        return;
    }

    g_assetDir = assetDir;
    // Ensure trailing slash for path safety
    if (g_assetDir.back() != '/') g_assetDir += "/";

    g_offsetToName.clear();

    if (!manifestBuf || manifestSize < 4) {
        LOGE("Init: FAILED - manifest buffer invalid (Size: %u)", manifestSize);
        return;
    }

    // Read total entry count from the first 4 bytes
    uint32_t entryCount = read_u32_le(manifestBuf);
    
    // RECORD_SIZE must be 48 to match: romOffset(4) + fileSize(4) + fileName(32) + padding(8)
    static const uint32_t RECORD_SIZE = 48; 
    uint32_t maxPossibleEntries = (manifestSize - 4) / RECORD_SIZE;
    
    if (entryCount > maxPossibleEntries) {
        LOGW("Init: entryCount (%u) exceeds buffer size. Clamping to %u", entryCount, maxPossibleEntries);
        entryCount = maxPossibleEntries;
    }

    const uint8_t* p = manifestBuf + 4;
    for (uint32_t i = 0; i < entryCount; ++i) {
        const uint8_t* record = p + (i * RECORD_SIZE);
        
        uint32_t romOffset = read_u32_le(record + 0);
        // Record + 4 is fileSize (not needed for the mapping phase)
        
        // Asset name starts at byte 8 and is up to 32 chars
        const char* namePtr = reinterpret_cast<const char*>(record + 8);
        
        if (namePtr[0] != '\0') {
            // We store the name to map the DMA request later
            g_offsetToName[romOffset] = std::string(namePtr, strnlen(namePtr, 32));
        }
    }

    LOGI("Init: SUCCESS. Dir: %s | %u assets ready.", g_assetDir.c_str(), (uint32_t)g_offsetToName.size());
}

/**
 * ResourceMgr_HandleDma
 * Intercepts game data requests and pulls from the extracted loose files.
 */
void ResourceMgr_HandleDma(void* dramAddr,
                           uint32_t devAddr,
                           uint32_t size) {
    if (g_assetDir.empty()) {
        LOGE("DMA: FAILED - ResourceMgr not initialized!");
        return;
    }
    if (!dramAddr || size == 0) return;

    // 1. Find the filename associated with this ROM address
    auto it = g_offsetToName.find(devAddr);
    if (it == g_offsetToName.end()) {
        // Log this to see which LinkerSymbols need adjusting
        LOGW("DMA: Cache Miss at 0x%08X (Requested %u bytes)", devAddr, size);
        memset(dramAddr, 0, size);
        return;
    }

    // 2. Open the file from the internal storage
    std::string filePath = g_assetDir + it->second;
    FILE* f = fopen(filePath.c_str(), "rb");
    
    if (!f) {
        LOGE("DMA: File Open Failed! Path: %s | Error: %s", filePath.c_str(), strerror(errno));
        memset(dramAddr, 0, size);
        return;
    }

    // 3. Read the extracted data
    fseek(f, 0, SEEK_END);
    long fileLen = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fileLen <= 0) {
        LOGE("DMA: File is empty or inaccessible: %s", it->second.c_str());
        fclose(f);
        memset(dramAddr, 0, size);
        return;
    }

    uint32_t copyLen = (uint32_t(fileLen) < size) ? uint32_t(fileLen) : size;
    size_t bytesRead = fread(dramAddr, 1, copyLen, f);
    fclose(f);

    // 4. Fill remainder with zero if file is smaller than request
    if (bytesRead < size) {
        memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
    }

    LOGI("DMA: Loaded %s (requested %u, read %zu)", it->second.c_str(), size, bytesRead);
    
    // Yield to avoid starving the audio/render threads during heavy IO
    sched_yield();
}

} // extern "C"
