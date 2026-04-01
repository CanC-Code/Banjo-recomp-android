#include "tools/rare_decompression.h"

#include <cstdint>
#include <cstdlib>
#include <cstring>

#include <zlib.h>
#include <android/log.h>

extern "C" {

uint8_t* decompress_rare_asset(const uint8_t* src,
                               uint32_t src_size,
                               uint32_t* out_size) {
    // Minimum: 2 bytes magic + 4 bytes decompressed length
    if (!src || src_size < 6) {
        return nullptr;
    }

    // Rare compression magic: 0x11 0x72
    if (src[0] != 0x11 || src[1] != 0x72) {
        return nullptr;
    }

    // Big-endian decompressed size
    uint32_t decompLen =
        (uint32_t(src[2]) << 24) |
        (uint32_t(src[3]) << 16) |
        (uint32_t(src[4]) << 8)  |
        (uint32_t(src[5]));

    // FIX: Sanity limit increased from 32 MB to 128 MB to support larger OTR assets
    const uint32_t MAX_DECOMPRESSED_SIZE = 128u * 1024u * 1024u;
    
    if (decompLen == 0 || decompLen > MAX_DECOMPRESSED_SIZE) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            "BKA_DECOMP",
            "Rare inflate aborted: invalid size (decompLen=%u). Cap is %u.",
            decompLen,
            MAX_DECOMPRESSED_SIZE
        );
        return nullptr;
    }

    uint8_t* outBuf = static_cast<uint8_t*>(malloc(decompLen));
    if (!outBuf) {
        __android_log_print(ANDROID_LOG_ERROR, "BKA_DECOMP", "Failed to allocate %u bytes", decompLen);
        return nullptr;
    }

    z_stream strm;
    std::memset(&strm, 0, sizeof(strm));

    // Compressed data begins immediately after:
    //   2 bytes magic + 4 bytes decompressed length = 6 bytes
    strm.next_in   = const_cast<Bytef*>(reinterpret_cast<const Bytef*>(src + 6));
    strm.avail_in  = src_size - 6;
    strm.next_out  = reinterpret_cast<Bytef*>(outBuf);
    strm.avail_out = decompLen;

    // Raw DEFLATE stream (no zlib or gzip headers)
    if (inflateInit2(&strm, -15) != Z_OK) {
        free(outBuf);
        return nullptr;
    }

    int ret = inflate(&strm, Z_FINISH);
    inflateEnd(&strm);

    // Must fully finish and exactly fill the output buffer
    if (ret != Z_STREAM_END || strm.avail_out != 0) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            "BKA_DECOMP",
            "Rare inflate failed (ret=%d, remaining=%u)",
            ret,
            strm.avail_out
        );
        free(outBuf);
        return nullptr;
    }

    if (out_size) {
        *out_size = decompLen;
    }

    return outBuf;
}

} // extern "C"
