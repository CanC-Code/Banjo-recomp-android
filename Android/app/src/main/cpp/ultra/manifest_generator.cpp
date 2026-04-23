#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <android/log.h>
#include <endian.h> // For be32toh (Big Endian to Host)

#define LOG_TAG "ManifestGenerator"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// In BK US v1.0, the DMA table typically starts around 0x10CD0.
// (Adjust this if you are using a different ROM version).
const uint32_t BK_DMA_TABLE_OFFSET = 0x10CD0; 
const uint32_t MAX_ASSETS = 9000; // BK has roughly ~8000-9000 assets

// Helper to write Little-Endian 32-bit values into our RAM buffer
static void write_u32_le(uint8_t* ptr, uint32_t val) {
    ptr[0] = (val & 0xFF);
    ptr[1] = ((val >> 8) & 0xFF);
    ptr[2] = ((val >> 16) & 0xFF);
    ptr[3] = ((val >> 24) & 0xFF);
}

extern "C" {

bool GenerateManifestFromROM(int romFd, uint8_t** outManifestBuf, uint32_t* outManifestSize) {
    LOGI("Scanning ROM for DMA Asset Table...");

    // Allocate memory to read the N64 DMA table (each entry is 8 bytes: Start, End)
    uint32_t dmaTableSize = MAX_ASSETS * 8;
    uint8_t* dmaTable = (uint8_t*)malloc(dmaTableSize);
    
    if (!dmaTable) {
        LOGE("Failed to allocate RAM for DMA table read.");
        return false;
    }

    // Read the DMA table directly from the ROM
    ssize_t bytesRead = pread(romFd, dmaTable, dmaTableSize, BK_DMA_TABLE_OFFSET);
    if (bytesRead <= 0) {
        LOGE("Failed to read ROM at DMA offset 0x%X", BK_DMA_TABLE_OFFSET);
        free(dmaTable);
        return false;
    }

    // Calculate how much RAM we need for the 4-byte header + 48-byte records
    *outManifestSize = 4 + (MAX_ASSETS * 48);
    *outManifestBuf = (uint8_t*)malloc(*outManifestSize);
    
    if (!*outManifestBuf) {
        LOGE("Failed to allocate RAM for the dynamic manifest.");
        free(dmaTable);
        return false;
    }

    // 1. Write the Entry Count Header (4 bytes)
    write_u32_le(*outManifestBuf, MAX_ASSETS);
    
    uint8_t* recordStart = *outManifestBuf + 4;
    uint32_t validAssets = 0;

    // 2. Loop through the N64 DMA table and build our manifest records
    for (uint32_t i = 0; i < MAX_ASSETS; i++) {
        uint8_t* dmaEntry = dmaTable + (i * 8);
        uint8_t* record   = recordStart + (i * 48);

        // N64 uses Big-Endian, so we must swap the bytes to read them correctly
        uint32_t romStart = be32toh(*(uint32_t*)(dmaEntry + 0));
        uint32_t romEnd   = be32toh(*(uint32_t*)(dmaEntry + 4));

        uint32_t fileSize = 0;
        if (romEnd > romStart && romStart != 0xFFFFFFFF) {
            fileSize = romEnd - romStart;
            validAssets++;
        }

        // Write Offset and Size (Little Endian format for the OTR builder)
        write_u32_le(record + 0, romStart);
        write_u32_le(record + 4, fileSize);

        // Generate a generic filename since the ROM doesn't contain names
        char fileName[33];
        snprintf(fileName, sizeof(fileName), "asset_%04u.bin", i);
        
        // Write the filename padded with zeroes
        memset(record + 8, 0, 40); 
        memcpy(record + 8, fileName, strlen(fileName));
    }

    LOGI("Dynamic manifest built! Found %u valid assets out of %u slots.", validAssets, MAX_ASSETS);

    free(dmaTable);
    return true;
}

} // extern "C"
