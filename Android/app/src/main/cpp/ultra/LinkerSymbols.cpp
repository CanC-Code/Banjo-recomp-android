#include <cstdint>

extern "C" {

/**
 * 1. Math Constants
 * In C++, 'const' globals have internal linkage by default. 
 * We remove 'const' here so the linker can export this symbol to the recompiled C code.
 */
uint32_t __libm_qnan_f = 0x7FC00000;

/**
 * 2. Segment and ROM Symbols
 * These symbols act as memory markers. Even if they point to 0, 
 * they must exist for the game logic to calculate offsets.
 */

// Core Code/Data
uintptr_t core1_VRAM = 0x80000000; 
uintptr_t core1_rzip_ROM_START = 0;
uintptr_t core1_rzip_ROM_END   = 0;
uintptr_t core2_rzip_ROM_START = 0;
uintptr_t core2_rzip_ROM_END   = 0;

// Levels & Cutscenes (Ordered by typical internal ID)
uintptr_t SM_rzip_ROM_START = 0;        // Spiral Mountain
uintptr_t SM_rzip_ROM_END   = 0;

uintptr_t MM_rzip_ROM_START = 0;        // Mumbo's Mountain
uintptr_t MM_rzip_ROM_END   = 0;

uintptr_t TTC_rzip_ROM_START = 0;       // Treasure Trove Cove
uintptr_t TTC_rzip_ROM_END   = 0;

uintptr_t CC_rzip_ROM_START = 0;        // Clanker's Cavern
uintptr_t CC_rzip_ROM_END   = 0;

uintptr_t BGS_rzip_ROM_START = 0;       // Bubblegloop Swamp
uintptr_t BGS_rzip_ROM_END   = 0;

uintptr_t FP_rzip_ROM_START = 0;        // Freezeezy Peak
uintptr_t FP_rzip_ROM_END   = 0;

uintptr_t GV_rzip_ROM_START = 0;        // Gobi's Valley
uintptr_t GV_rzip_ROM_END   = 0;

uintptr_t MMM_rzip_ROM_START = 0;       // Mad Monster Mansion
uintptr_t MMM_rzip_ROM_END   = 0;

uintptr_t RBB_rzip_ROM_START = 0;       // Rusty Bucket Bay
uintptr_t RBB_rzip_ROM_END   = 0;

uintptr_t CCW_rzip_ROM_START = 0;       // Click Clock Wood
uintptr_t CCW_rzip_ROM_END   = 0;

uintptr_t lair_rzip_ROM_START = 0;      // Gruntilda's Lair
uintptr_t lair_rzip_ROM_END   = 0;

uintptr_t fight_rzip_ROM_START = 0;     // Final Battle
uintptr_t fight_rzip_ROM_END   = 0;

uintptr_t cutscenes_rzip_ROM_START = 0; // Cutscene Overlays
uintptr_t cutscenes_rzip_ROM_END   = 0;

uintptr_t emptyLvl_rzip_ROM_START = 0;
uintptr_t emptyLvl_rzip_ROM_END   = 0;

/**
 * 3. Tables & Metadata
 */
uintptr_t gOverlayTable = 0;

} // extern "C"
