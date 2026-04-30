#include <cstdint>

extern "C" {

/**
 * 1. Math Constants
 * These are required by the recompiled math functions (cosf, sinf, etc.)
 */
const uint32_t __libm_qnan_f = 0x7FC00000;

/**
 * 2. Segment and ROM Symbols
 * The recompiled code uses these to calculate DMA transfers and VRAM locations.
 * We define them as char arrays so they have a memory address the linker can bind to.
 */

// Core Segments
uintptr_t core1_VRAM = 0x80000000; 
uintptr_t core1_rzip_ROM_START = 0;
uintptr_t core1_rzip_ROM_END   = 0;

uintptr_t core2_rzip_ROM_START = 0;
uintptr_t core2_rzip_ROM_END   = 0;

// Level/Overlay ROM Markers
uintptr_t emptyLvl_rzip_ROM_START = 0;
uintptr_t emptyLvl_rzip_ROM_END   = 0;

uintptr_t CC_rzip_ROM_START = 0;
uintptr_t CC_rzip_ROM_END   = 0;

uintptr_t MMM_rzip_ROM_START = 0;
uintptr_t MMM_rzip_ROM_END   = 0;

uintptr_t GV_rzip_ROM_START = 0;
uintptr_t GV_rzip_ROM_END   = 0;

uintptr_t TTC_rzip_ROM_START = 0;
uintptr_t TTC_rzip_ROM_END   = 0;

uintptr_t MM_rzip_ROM_START = 0;
uintptr_t MM_rzip_ROM_END   = 0;

uintptr_t BGS_rzip_ROM_START = 0;
uintptr_t BGS_rzip_ROM_END   = 0;

/**
 * 3. The Overlay Table
 * This is usually a struct array. We provide a pointer/placeholder here.
 * If your game crashes during level load, we will need to populate this
 * with the actual overlay metadata.
 */
uintptr_t gOverlayTable = 0;

} // extern "C"
