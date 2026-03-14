#include <sched.h>

#include <map>
#include <string>
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

#include <android/log.h>

#include "tools/rare_decompression.h"

#define LOG_TAG "ResourceMgr"

#pragma pack(push, 1)
struct AssetEntry {
    uint32_t offset;
    char type[8];
    char name[32];
};
#pragma pack(pop)

static std::map<uint32_t, AssetEntry> g_manifest;
static std::string g_otrPath;

extern "C" {

/**
 * Initializes the Resource Manager with the path to the OTR file
 * and the manifest buffer loaded from Android assets.
 */
void ResourceMgr_Init(const char* otrPath,
                      uint8_t* manifestBuf,
                      uint32_t manifestSize) {
    if (!otrPath) {
        return;
    }

    g_otrPath = otrPath;
    g_manifest.clear();

    if (!manifestBuf || manifestSize < 4) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG,
                            "Invalid manifest buffer provided");
        return;
    }

    // Manifest entry count is little-endian
    uint32_t entryCount =
        (uint32_t(manifestBuf[0])      ) |
        (uint32_t(manifestBuf[1]) <<  8) |
        (uint32_t(manifestBuf[2]) << 16) |
        (uint32_t(manifestBuf[3]) << 24);

    uint32_t maxEntries =
        (manifestSize - 4) / sizeof(AssetEntry);

    if (entryCount > maxEntries) {
        __android_log_print(
            ANDROID_LOG_WARN,
            LOG_TAG,
            "Manifest entry count clamped (%u -> %u)",
            entryCount,
            maxEntries
        );
        entryCount = maxEntries;
    }

    const AssetEntry* entries =
        reinterpret_cast<const AssetEntry*>(manifestBuf + 4);

    for (uint32_t i = 0; i < entryCount; ++i) {
        g_manifest[entries[i].offset] = entries[i];
    }

    __android_log_print(
        ANDROID_LOG_INFO,
        LOG_TAG,
        "Loaded %u asset entries from manifest",
        entryCount
    );
}

/**
 * Handles N64-style DMA requests.
 * Detects Rare (0x1172) compression and decompresses on the fly.
 */
void ResourceMgr_HandleDma(void* dramAddr,
                           uint32_t devAddr,
                           uint32_t size) {
    if (g_otrPath.empty()) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            LOG_TAG,
            "DMA before ResourceMgr_Init"
        );
        return;
    }

    if (!dramAddr || size == 0) {
        return;
    }

    FILE* f = fopen(g_otrPath.c_str(), "rb");
    if (!f) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            LOG_TAG,
            "Failed to open OTR: %s",
            g_otrPath.c_str()
        );
        return;
    }

    if (fseek(f, devAddr, SEEK_SET) != 0) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            LOG_TAG,
            "fseek failed at 0x%08X",
            devAddr
        );
        fclose(f);
        return;
    }

    // Read header to detect Rare compression
    uint8_t header[6];
    size_t headerRead = fread(header, 1, sizeof(header), f);

    bool isCompressed =
        (headerRead == 6 &&
         header[0] == 0x11 &&
         header[1] == 0x72);

    // Reset file pointer
    fseek(f, devAddr, SEEK_SET);

    if (isCompressed) {
        // Read the entire DMA block (compressed)
        std::vector<uint8_t> compressed(size);
        size_t bytesRead =
            fread(compressed.data(), 1, size, f);

        uint32_t outSize = 0;
        uint8_t* decompressed =
            decompress_rare_asset(
                compressed.data(),
                static_cast<uint32_t>(bytesRead),
                &outSize
            );

        if (!decompressed) {
            __android_log_print(
                ANDROID_LOG_ERROR,
                LOG_TAG,
                "Rare decompression failed at 0x%08X",
                devAddr
            );
            fclose(f);
            return;
        }

        memcpy(dramAddr, decompressed, outSize);
        free(decompressed);
    } else {
        // Standard DMA copy
        fread(dramAddr, 1, size, f);
    }

    fclose(f);

    // Yield CPU during heavy IO / decompression
    sched_yield();
}

} // extern "C"