#include <cstdint>

#define RECOMP_SYMBOL __attribute__((used)) __attribute__((visibility("default")))

extern "C" {

/**
 * 1. Math Constants
 */
RECOMP_SYMBOL uint32_t __libm_qnan_f = 0x7FC00000;

/**
 * 2. Memory & ROM Markers
 * These must match the 'romOffset' values in your manifest_us.bin.
 * The engine uses these to request data from the Resource Manager.
 */

// Core Engine Segments
RECOMP_SYMBOL uintptr_t core1_VRAM           = 0x80001000; 
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_START = 0x00001050; // Typical Core1 Offset
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_END   = 0x000E0000;

RECOMP_SYMBOL uintptr_t core2_rzip_ROM_START = 0x000F0000; // Typical Core2 Offset
RECOMP_SYMBOL uintptr_t core2_rzip_ROM_END   = 0x001F0000;

// Levels (Magic keys for the Resource Manager)
RECOMP_SYMBOL uintptr_t SM_rzip_ROM_START   = 0x00400000; // Spiral Mountain
RECOMP_SYMBOL uintptr_t SM_rzip_ROM_END     = 0x00410000;
RECOMP_SYMBOL uintptr_t MM_rzip_ROM_START   = 0x00500000; // Mumbo's Mountain
RECOMP_SYMBOL uintptr_t MM_rzip_ROM_END     = 0x00510000;
RECOMP_SYMBOL uintptr_t TTC_rzip_ROM_START  = 0x00600000; // Treasure Trove Cove
RECOMP_SYMBOL uintptr_t TTC_rzip_ROM_END    = 0x00610000;
RECOMP_SYMBOL uintptr_t CC_rzip_ROM_START   = 0x00700000; // Clanker's Cavern
RECOMP_SYMBOL uintptr_t CC_rzip_ROM_END     = 0x00710000;
RECOMP_SYMBOL uintptr_t BGS_rzip_ROM_START  = 0x00800000; // Bubblegloop Swamp
RECOMP_SYMBOL uintptr_t BGS_rzip_ROM_END    = 0x00810000;
RECOMP_SYMBOL uintptr_t FP_rzip_ROM_START   = 0x00900000; // Freezeezy Peak
RECOMP_SYMBOL uintptr_t FP_rzip_ROM_END     = 0x00910000;
RECOMP_SYMBOL uintptr_t GV_rzip_ROM_START   = 0x00A00000; // Gobi's Valley
RECOMP_SYMBOL uintptr_t GV_rzip_ROM_END     = 0x00A10000;
RECOMP_SYMBOL uintptr_t MMM_rzip_ROM_START  = 0x00B00000; // Mad Monster Mansion
RECOMP_SYMBOL uintptr_t MMM_rzip_ROM_END    = 0x00B10000;
RECOMP_SYMBOL uintptr_t RBB_rzip_ROM_START  = 0x00C00000; // Rusty Bucket Bay
RECOMP_SYMBOL uintptr_t RBB_rzip_ROM_END    = 0x00C10000;
RECOMP_SYMBOL uintptr_t CCW_rzip_ROM_START  = 0x00D00000; // Click Clock Wood
RECOMP_SYMBOL uintptr_t CCW_rzip_ROM_END    = 0x00D10000;

// System Overlays
RECOMP_SYMBOL uintptr_t lair_rzip_ROM_START      = 0x00E00000;
RECOMP_SYMBOL uintptr_t lair_rzip_ROM_END        = 0x00E10000;
RECOMP_SYMBOL uintptr_t fight_rzip_ROM_START     = 0x00F00000;
RECOMP_SYMBOL uintptr_t fight_rzip_ROM_END       = 0x00F10000;
RECOMP_SYMBOL uintptr_t cutscenes_rzip_ROM_START = 0x01000000;
RECOMP_SYMBOL uintptr_t cutscenes_rzip_ROM_END   = 0x01010000;
RECOMP_SYMBOL uintptr_t emptyLvl_rzip_ROM_START  = 0x01100000;
RECOMP_SYMBOL uintptr_t emptyLvl_rzip_ROM_END    = 0x01110000;

RECOMP_SYMBOL uintptr_t gOverlayTable = 0x01200000;

} // extern "C"
