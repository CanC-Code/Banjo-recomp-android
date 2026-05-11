#include "rare_decompression.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <zlib.h>
#include <android/log.h>

#define LOG_TAG "BKA_DECOMP"

extern "C" {

uint8_t* decompress_rare_asset(const uint8_t* src,
                               uint32_t src_size,
                               uint32_t* out_size) {
    // 1. Safety Guard: Basic size check
    if (!src || src_size < 6) {
        return nullptr;
    }

    // 2. Magic Check: Rare compression starts with 0x1172.
    // If this fails (e.g., for ipl3, which is raw code), we return nullptr.
    // The caller (otr_builder) must handle nullptr as "Use Raw Data."
    if (src[0] != 0x11 || src[1] != 0x72) {
        return nullptr;
    }

    // 3. Size Header: Big-endian 4-byte decompressed length
    uint32_t decompLen =
        (uint32_t(src[2]) << 24) |
        (uint32_t(src[3]) << 16) |
        (uint32_t(src[4]) << 8)  |
        (uint32_t(src[5]));

    // Sanity Check: Avoid massive allocations that crash the Android heap
    const uint32_t MAX_DECOMPRESSED_SIZE = 64u * 1024u * 1024u; // 64MB cap

    if (decompLen == 0 || decompLen > MAX_DECOMPRESSED_SIZE) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, 
            "Aborted: Invalid size header (%u bytes). Check ROM endianness.", decompLen);
        return nullptr;
    }

    uint8_t* outBuf = static_cast<uint8_t*>(malloc(decompLen));
    if (!outBuf) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "OOM: Could not allocate %u bytes", decompLen);
        return nullptr;
    }

    // 4. Zlib Setup: Standard Deflate
    z_stream strm;
    std::memset(&strm, 0, sizeof(strm));

    // Data starts after the 6-byte header (0x1172 + 4-byte size)
    strm.next_in   = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(src + 6));
    strm.avail_in  = src_size - 6;
    strm.next_out  = reinterpret_cast<Bytef*>(outBuf);
    strm.avail_out = decompLen;

    // Use -15 for raw DEFLATE (no zlib/gzip headers)
    if (inflateInit2(&strm, -15) != Z_OK) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, "inflateInit2 failed");
        free(outBuf);
        return nullptr;
    }

    int ret = inflate(&strm, Z_FINISH);
    inflateEnd(&strm);

    // 5. Validation: Ensure the stream finished correctly
    if (ret != Z_STREAM_END) {
        __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, 
            "Decompression error: %d (In: %u, Out: %u/%u)", 
            ret, src_size - 6, strm.total_out, decompLen);
        free(outBuf);
        return nullptr;
    }

    if (out_size) {
        *out_size = decompLen;
    }

    return outBuf;
}

} // extern "C"
