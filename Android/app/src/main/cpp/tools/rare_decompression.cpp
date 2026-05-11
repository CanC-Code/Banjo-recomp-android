// File: Android/app/src/main/cpp/tools/rare_decompression.cpp
#include "rare_decompression.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <zlib.h>
#include <android/log.h>

#define LOG_TAG "BKA_DECOMP"
#define CHUNK_SIZE 32768 // 32KB chunks for dynamic buffer resizing

extern "C" {

uint8_t* decompress_rare_asset(const uint8_t* src,
                               uint32_t src_size,
                               uint32_t* out_size) {
    // 1. Safety Guard: Basic size check
    if (!src || src_size < 6) {
        return nullptr;
    }

    // 2. Magic Check: Rare compression starts with 0x1172.
    if (src[0] != 0x11 || src[1] != 0x72) {
        return nullptr;
    }

    // 3. Size Header: Big-endian 4-byte decompressed length
    // We only use this as an initial capacity hint now, not a strict constraint.
    uint32_t expectedLen =
        (uint32_t(src[2]) << 24) |
        (uint32_t(src[3]) << 16) |
        (uint32_t(src[4]) << 8)  |
        (uint32_t(src[5]));

    // 4. Zlib Setup: Standard Deflate
    z_stream strm;
    std::memset(&strm, 0, sizeof(strm));

    // Compressed payload starts immediately after the 6-byte header
    strm.next_in   = const_cast<Bytef*>(src + 6);
    strm.avail_in  = src_size - 6;

    // Use -15 for raw DEFLATE (matches Python's wbits=-15)
    if (inflateInit2(&strm, -15) != Z_OK) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "inflateInit2 failed");
        return nullptr;
    }

    // 5. Dynamic Chunked Decompression (Mimics Python's dynamic allocation)
    std::vector<uint8_t> outData;
    
    // Reserve memory safely to prevent OOM on corrupt headers
    if (expectedLen > 0 && expectedLen < 64u * 1024u * 1024u) {
        outData.reserve(expectedLen);
    } else {
        outData.reserve(CHUNK_SIZE);
    }

    uint8_t outChunk[CHUNK_SIZE];
    int ret;

    // Decompress chunk by chunk until the stream naturally ends
    do {
        strm.next_out = outChunk;
        strm.avail_out = CHUNK_SIZE;
        
        // Z_NO_FLUSH allows zlib to dynamically adapt to padding
        ret = inflate(&strm, Z_NO_FLUSH);
        
        if (ret == Z_NEED_DICT || ret == Z_DATA_ERROR || ret == Z_MEM_ERROR) {
            __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "Zlib decompression failed: %d", ret);
            inflateEnd(&strm);
            return nullptr;
        }
        
        uint32_t bytesDecompressed = CHUNK_SIZE - strm.avail_out;
        outData.insert(outData.end(), outChunk, outChunk + bytesDecompressed);
        
    } while (strm.avail_out == 0);

    inflateEnd(&strm);

    // 6. Finalize and copy back to a standard C-buffer for the JNI bridge
    if (outData.empty()) {
        return nullptr;
    }

    uint8_t* finalBuf = static_cast<uint8_t*>(malloc(outData.size()));
    if (!finalBuf) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "Failed to allocate final buffer");
        return nullptr;
    }
    
    std::memcpy(finalBuf, outData.data(), outData.size());
    if (out_size) {
        *out_size = static_cast<uint32_t>(outData.size());
    }

    return finalBuf;
}

} // extern "C"
