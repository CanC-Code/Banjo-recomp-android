#ifndef ASSETS_MANIFEST_H
#define ASSETS_MANIFEST_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#pragma pack(push, 1)

enum AssetType {
    ASSET_TYPE_SKIP = 0,
    ASSET_TYPE_COMPRESSED = 1,
    ASSET_TYPE_RAW = 2
};

struct AssetEntry {
    uint32_t romOffset;
    uint32_t compSize;
    uint32_t decompSize;
    uint32_t type;
    char name[128]; // Ensure this matches your Python struct.pack size
};

struct ManifestHeader {
    uint32_t magic;      // 0x424B414D ('BKAM')
    uint32_t entryCount;
    uint32_t version;
};

#pragma pack(pop)

#ifdef __cplusplus
}
#endif

#endif
