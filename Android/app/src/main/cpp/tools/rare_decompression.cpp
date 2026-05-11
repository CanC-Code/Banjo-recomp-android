// File: Android/app/src/main/cpp/tools/rare_decompression.cpp
#include "rare_decompression.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <zlib.h>
#include <android/log.h>

#define LOG_TAG "BKA_DECOMP"
#define CHUNK_SIZE 32768

extern "C" {

uint8_t* decompress_rare_asset(const uint8_t* src,
                               uint32_t src_size,
                               uint32_t* out_size) {
    // 1. Safety Guard
    if (!src || src_size < 6) return nullptr;
    if (src[0] != 0x11 || src[1] != 0x72) return nullptr;

    // 2. Zlib Setup
    z_stream strm;
    std::memset(&strm, 0, sizeof(strm));

    strm.next_in   = const_cast<Bytef*>(src + 6);
    strm.avail_in  = src_size - 6;

    if (inflateInit2(&strm, -15) != Z_OK) return nullptr;

    // 3. Pure C Memory Allocation (Prevents std::bad_alloc crashes)
    uint32_t currentCapacity = CHUNK_SIZE;
    uint8_t* outBuf = static_cast<uint8_t*>(malloc(currentCapacity));
    if (!outBuf) {
        inflateEnd(&strm);
        return nullptr;
    }

    uint32_t totalOut = 0;
    int ret;

    // 4. Dynamic Chunked Decompression Loop
    do {
        // Expand buffer safely if we are running out of room
        if (totalOut + CHUNK_SIZE > currentCapacity) {
            
            // Hard Cap: Prevent runaway allocations over 64MB on corrupt assets
            if (currentCapacity >= 64u * 1024u * 1024u) {
                __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "Decompression exceeded 64MB cap. Aborting.");
                free(outBuf);
                inflateEnd(&strm);
                return nullptr;
            }
            
            currentCapacity *= 2;
            uint8_t* newBuf = static_cast<uint8_t*>(realloc(outBuf, currentCapacity));
            
            // If the Android heap denies the allocation, gracefully fail instead of crashing
            if (!newBuf) {
                __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "OOM: Failed to realloc to %u bytes.", currentCapacity);
                free(outBuf);
                inflateEnd(&strm);
                return nullptr;
            }
            outBuf = newBuf;
        }

        strm.next_out = outBuf + totalOut;
        strm.avail_out = CHUNK_SIZE;

        ret = inflate(&strm, Z_NO_FLUSH);

        // Catch corrupt zlib stream data
        if (ret == Z_STREAM_ERROR || ret == Z_DATA_ERROR || ret == Z_MEM_ERROR || ret == Z_NEED_DICT) {
            free(outBuf);
            inflateEnd(&strm);
            return nullptr;
        }

        uint32_t bytesDecompressed = CHUNK_SIZE - strm.avail_out;
        totalOut += bytesDecompressed;

    // Continue until the stream ends naturally or runs out of valid input (Z_BUF_ERROR)
    } while (ret != Z_STREAM_END && ret != Z_BUF_ERROR);

    inflateEnd(&strm);

    // 5. Validation
    if (totalOut == 0) {
        free(outBuf);
        return nullptr;
    }

    if (out_size) *out_size = totalOut;
    return outBuf;
}

} // extern "C"
