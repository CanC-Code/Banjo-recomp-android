#include <cstdint>

extern "C" {

/**
 * 1. Math Constants
 */
uint32_t __libm_qnan_f = 0x7FC00000;

/**
 * 2. Segment and ROM Symbols
 * We are giving these unique "Magic" addresses. 
 * When the game asks to DMA from 0x1000, the ResourceMgr will 
 * look at the manifest and know that 0x1000 = "core1.otr".
 */

// Core Code/Data
uintptr_t core1_VRAM           = 0x80001000; 
uintptr_t core1_rzip_ROM_START = 0x00001000; // Magic Key for Core1
uintptr_t core1_rzip_ROM_END   = 0x00010000;

uintptr_t core2_rzip_ROM_START = 0x00020000; // Magic Key for Core2
uintptr_t core2_rzip_ROM_END   = 0x00030000;

// Level/Overlay ROM Markers
// If your manifest uses different offsets, update these to match!
uintptr_t SM_rzip_ROM_START   = 0x00100000; // Spiral Mountain
uintptr_t SM_rzip_ROM_END     = 0x00110000;

uintptr_t MM_rzip_ROM_START   = 0x00200000; // Mumbo's Mountain
uintptr_t MM_rzip_ROM_END     = 0x00210000;

uintptr_t TTC_rzip_ROM_START  = 0x00300000; // Treasure Trove Cove
uintptr_t TTC_rzip_ROM_END    = 0x00310000;

uintptr_t CC_rzip_ROM_START   = 0x00400000; // Clanker's Cavern
uintptr_t CC_rzip_ROM_END     = 0x00410000;

uintptr_t BGS_rzip_ROM_START  = 0x00500000; // Bubblegloop Swamp
uintptr_t BGS_rzip_ROM_END    = 0x00510000;

uintptr_t FP_rzip_ROM_START   = 0x00600000; // Freezeezy Peak
uintptr_t FP_rzip_ROM_END     = 0x00610000;

uintptr_t GV_rzip_ROM_START   = 0x00700000; // Gobi's Valley
uintptr_t GV_rzip_ROM_END     = 0x00710000;

uintptr_t MMM_rzip_ROM_START  = 0x00800000; // Mad Monster Mansion
uintptr_t MMM_rzip_ROM_END    = 0x00810000;

uintptr_t RBB_rzip_ROM_START  = 0x00900000; // Rusty Bucket Bay
uintptr_t RBB_rzip_ROM_END    = 0x00910000;

uintptr_t CCW_rzip_ROM_START  = 0x00A00000; // Click Clock Wood
uintptr_t CCW_rzip_ROM_END    = 0x00A10000;

uintptr_t lair_rzip_ROM_START = 0x00B00000; // Gruntilda's Lair
uintptr_t lair_rzip_ROM_END   = 0x00B10000;

uintptr_t fight_rzip_ROM_START = 0x00C00000; // Final Battle
uintptr_t fight_rzip_ROM_END   = 0x00C10000;

uintptr_t cutscenes_rzip_ROM_START = 0x00D00000; 
uintptr_t cutscenes_rzip_ROM_END   = 0x00D10000;

uintptr_t emptyLvl_rzip_ROM_START = 0x00E00000;
uintptr_t emptyLvl_rzip_ROM_END   = 0x00E10000;

/**
 * 3. Tables & Metadata
 * This should technically point to an actual table, but we'll 
 * start with a non-zero marker to see if the game tries to access it.
 */
uintptr_t gOverlayTable = 0x00F00000;

} // extern "C"
