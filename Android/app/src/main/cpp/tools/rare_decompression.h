#ifndef RARE_DECOMPRESSION_H
#define RARE_DECOMPRESSION_H

#include <stdint.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Decompresses a Rare asset starting with the 0x1172 header.
 * * @param src Pointer to the start of the compressed data.
 * @param src_size Size of the input buffer (needed for bounds checking).
 * @param out_size Pointer to store the resulting decompressed size.
 * @return Pointer to the decompressed buffer (caller must free()).
 */
uint8_t* decompress_rare_asset(const uint8_t* src, uint32_t src_size, uint32_t* out_size);

#ifdef __cplusplus
}
#endif

#endif // RARE_DECOMPRESSION_H
