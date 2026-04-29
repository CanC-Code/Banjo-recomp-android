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
#include "ultra/assets_manifest.h"

#define LOG_TAG "ResourceMgr"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO,  LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN,  LOG_TAG, __VA_ARGS__)

// -----------------------------------------------------------------------
// Internal state
// -----------------------------------------------------------------------

// Maps a ROM-address offset -> asset name (e.g. "0x01234567" -> "banjo_tex_001")
static std::map<uint32_t, std::string> g_offsetToName;
// The directory where otr_builder wrote all the loose asset files.
static std::string g_assetDir;

extern "C" {

// -----------------------------------------------------------------------
// ResourceMgr_Init
//
// Called from nativeGameBoot with:
//   assetDir  – path to getFilesDir() where loose files live
//   manifestBuf / manifestSize – the manifest_us.bin from the APK assets,
//                                used to rebuild the offset->name map.
//
// Manifest binary layout (written by generate_manifest.py):
//   [4 bytes LE]  entryCount
//   then entryCount * ManifestEntry records:
//     [4 bytes LE]  romOffset
//     [4 bytes LE]  compSize   (not used here, for reference)
//     [4 bytes LE]  decompSize (not used here)
//     [4 bytes LE]  type       (AssetType enum)
//     [128 bytes]   name       (null-terminated asset filename)
// Total per record: 16 + 128 = 144 bytes
// -----------------------------------------------------------------------
void ResourceMgr_Init(const char* assetDir,
                      uint8_t*    manifestBuf,
                      uint32_t    manifestSize) {
    if (!assetDir || assetDir[0] == '\0') {
        LOGE("ResourceMgr_Init: null or empty assetDir");
        return;
    }

    g_assetDir = assetDir;
    g_offsetToName.clear();

    if (!manifestBuf || manifestSize < 4) {
        LOGE("ResourceMgr_Init: invalid manifest");
        return;
    }

    // Read entry count (little-endian)
    uint32_t entryCount =
        (uint32_t(manifestBuf[0])      ) |
        (uint32_t(manifestBuf[1]) <<  8) |
        (uint32_t(manifestBuf[2]) << 16) |
        (uint32_t(manifestBuf[3]) << 24);

    // Each record is sizeof(ManifestHeader fields per entry):
    //   romOffset(4) + compSize(4) + decompSize(4) + type(4) + name(128) = 144 bytes
    static const uint32_t RECORD_SIZE = 144;
    uint32_t maxEntries = (manifestSize - 4) / RECORD_SIZE;
    if (entryCount > maxEntries) {
        LOGW("Manifest entry count clamped (%u -> %u)", entryCount, maxEntries);
        entryCount = maxEntries;
    }

    const uint8_t* p = manifestBuf + 4;
    for (uint32_t i = 0; i < entryCount; ++i, p += RECORD_SIZE) {
        uint32_t romOffset =
            (uint32_t(p[0])      ) |
            (uint32_t(p[1]) <<  8) |
            (uint32_t(p[2]) << 16) |
            (uint32_t(p[3]) << 24);
        // Skip compSize(4), decompSize(4), type(4) = 12 bytes
        const char* name = reinterpret_cast<const char*>(p + 16);
        if (name[0] != '\0') {
            g_offsetToName[romOffset] = std::string(name, strnlen(name, 128));
        }
    }

    LOGI("ResourceMgr_Init: dir='%s', %u entries mapped", assetDir, entryCount);
}

// -----------------------------------------------------------------------
// ResourceMgr_HandleDma
//
// The game calls osPiRawStartDma / osEPiStartDma with a ROM cart address
// (devAddr) and wants the data copied to dramAddr.
//
// We look up the devAddr in our offset->name table, open the corresponding
// loose file from the asset directory, and copy it into DRAM.
// -----------------------------------------------------------------------
void ResourceMgr_HandleDma(void*    dramAddr,
                           uint32_t devAddr,
                           uint32_t size) {
    if (g_assetDir.empty()) {
        LOGE("DMA called before ResourceMgr_Init (devAddr=0x%08X)", devAddr);
        return;
    }
    if (!dramAddr || size == 0) return;

    // --- 1. Look up the asset name for this ROM address ---
    auto it = g_offsetToName.find(devAddr);
    if (it == g_offsetToName.end()) {
        // Not in manifest — zero-fill and warn (some ranges are BSS / padding)
        LOGW("DMA miss: no asset for devAddr=0x%08X size=%u (zero-filling)", devAddr, size);
        memset(dramAddr, 0, size);
        return;
    }

    // --- 2. Build the full path to the loose file ---
    std::string filePath = g_assetDir + "/" + it->second;

    FILE* f = fopen(filePath.c_str(), "rb");
    if (!f) {
        LOGE("DMA open failed: '%s'", filePath.c_str());
        memset(dramAddr, 0, size);
        return;
    }

    // --- 3. Read the file ---
    fseek(f, 0, SEEK_END);
    long fileLen = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fileLen <= 0) {
        LOGE("DMA empty file: '%s'", filePath.c_str());
        fclose(f);
        memset(dramAddr, 0, size);
        return;
    }

    // Read up to `size` bytes.  The file is already decompressed (otr_builder
    // decompressed it on extraction), so we copy directly.
    uint32_t copyLen = (uint32_t(fileLen) < size) ? uint32_t(fileLen) : size;
    size_t bytesRead = fread(dramAddr, 1, copyLen, f);
    fclose(f);

    // Zero-fill the remainder if the file is shorter than the DMA request
    if (bytesRead < size) {
        memset(static_cast<uint8_t*>(dramAddr) + bytesRead, 0, size - bytesRead);
    }

    // Yield after heavy IO so other threads get CPU time
    sched_yield();
}

} // extern "C"
