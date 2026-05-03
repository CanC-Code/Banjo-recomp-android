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
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// --- Manifest Structure (Must match otr_builder.cpp exactly) ---
#pragma pack(push, 1)
struct ManifestEntry {
    uint32_t offset;
    uint32_t size;
    char name[32];
    char type[8];
};
#pragma pack(pop)

static std::map<uint32_t, std::string> g_offsetToName;
static std::string g_assetDir;

// Helper to read Little-Endian uint32 (matching Python's '<I')
static uint32_t read_u32_le(const uint8_t* p) {
    return (uint32_t(p[0])) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}

extern "C" {

/**
 * Initializes the Resource Manager by mapping ROM offsets to extracted file names.
 * @param assetDir The directory where .bin files were extracted (e.g., internal storage)
 * @param manifestBuf The raw bytes of manifest_*.bin loaded from disk
 * @param manifestSize The size of the manifest buffer
 */
void ResourceMgr_Init(const char* assetDir, uint8_t* manifestBuf, uint32_t manifestSize) {
    if (!assetDir || !manifestBuf || manifestSize < 4) {
        LOGE("ResourceMgr_Init: Invalid arguments or empty manifest.");
        return;
    }

    g_assetDir = assetDir;
    // Ensure trailing slash for path concatenation
    if (!g_assetDir.empty() && g_assetDir.back() != '/') {
        g_assetDir += "/";
    }

    g_offsetToName.clear();

    // The first 4 bytes of our manifest_*.bin is the entry count
    uint32_t entryCount = read_u32_le(manifestBuf);
    
    // Verify we have enough data in the buffer for the promised entries
    if (4 + (entryCount * sizeof(ManifestEntry)) > manifestSize) {
        LOGE("ResourceMgr_Init: Manifest buffer is too small for %u entries.", entryCount);
        return;
    }

    // Cast the buffer (skipping the 4-byte count) to our struct array
    const ManifestEntry* entries = reinterpret_cast<const ManifestEntry*>(manifestBuf + 4);

    for (uint32_t i = 0; i < entryCount; ++i) {
        uint32_t romOffset = entries[i].offset;
        
        // Convert the 32-char name buffer to a safe std::string
        // strnlen handles cases where the name is not null-terminated
        std::string name(entries[i].name, strnlen(entries[i].name, 32));

        if (!name.empty()) {
            g_offsetToName[romOffset] = name;
        }
    }

    LOGI("ResourceMgr: Successfully mapped %zu assets from %s", g_offsetToName.size(), assetDir);
}

/**
 * Handles N64 DMA requests by loading the corresponding extracted .bin file into DRAM.
 * @param dramAddr The destination address in the N64's emulated RAM
 * @param devAddr The source address (ROM offset) requested by the game
 * @param size The number of bytes to transfer
 */
void ResourceMgr_HandleDma(void* dramAddr, uint32_t devAddr, uint32_t size) {
    // Look up the filename associated with this ROM offset
    auto it = g_offsetToName.find(devAddr);
    
    if (it == g_offsetToName.end()) {
        LOGE("DMA Fail: No asset found at ROM offset 0x%08X. Filling DRAM with 0.", devAddr);
        memset(dramAddr, 0, size);
        return;
    }

    // Construct the full path: /data/user/0/com.bkawrapper/files/extracted_assets/name.bin
    std::string fullPath = g_assetDir + it->second;
    
    FILE* f = fopen(fullPath.c_str(), "rb");
    if (!f) {
        LOGE("DMA Fail: Cannot open file %s (Error: %s)", fullPath.c_str(), strerror(errno));
        memset(dramAddr, 0, size);
        return;
    }

    // Read the file content directly into the emulated DRAM
    size_t bytesRead = fread(dramAddr, 1, size, f);
    fclose(f);

    // If the file on disk was smaller than the DMA request, zero-pad the rest
    if (bytesRead < size) {
        memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
        LOGW("DMA Warning: File %s was smaller than requested size %u.", it->second.c_str(), size);
    }

    LOGI("DMA Success: Loaded %s (Offset: 0x%08X, Size: %u)", it->second.c_str(), devAddr, size);
    
    // Yield thread to prevent the DMA hook from starving the main emulation thread
    sched_yield();
}

} // extern "C"
