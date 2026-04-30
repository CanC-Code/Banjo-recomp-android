#include <cstdint>

// Macro collision fix: The N64 headers define these as numbers. 
// We need to undefine them so we can declare them as pointers.
#undef RI_CONFIG_REG
#undef RI_CURRENT_LOAD_REG
#undef RI_SELECT_REG
#undef RI_REFRESH_REG
#undef PI_STATUS_REG
#undef VI_STATUS_REG

#define RECOMP_SYMBOL __attribute__((used)) __attribute__((visibility("default")))

extern "C" {

/**
 * 1. Hardware Register Mappings
 * Maps N64 hardware addresses to our safe buffer in NativeBridge.cpp
 */
extern uint32_t* gN64_Reg_Base;

// RI (RAM Interface) - Faulted at 0xA4800018
RECOMP_SYMBOL uint32_t* RI_CONFIG_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x00);
RECOMP_SYMBOL uint32_t* RI_CURRENT_LOAD_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x04);
RECOMP_SYMBOL uint32_t* RI_SELECT_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x18);
RECOMP_SYMBOL uint32_t* RI_REFRESH_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x10);

// PI (Peripheral Interface)
RECOMP_SYMBOL uint32_t* PI_STATUS_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x100);

// VI (Video Interface)
RECOMP_SYMBOL uint32_t* VI_STATUS_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x200);

/**
 * 2. Math Constants
 */
RECOMP_SYMBOL uint32_t __libm_qnan_f = 0x7FC00000;

/**
 * 3. Memory & ROM Markers
 */
RECOMP_SYMBOL uintptr_t core1_VRAM           = 0x80001000; 
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_START = 0x00001050;
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_END   = 0x000E0000;

RECOMP_SYMBOL uintptr_t core2_rzip_ROM_START = 0x000F0000;
RECOMP_SYMBOL uintptr_t core2_rzip_ROM_END   = 0x001F0000;

RECOMP_SYMBOL uintptr_t SM_rzip_ROM_START   = 0x00400000;
RECOMP_SYMBOL uintptr_t SM_rzip_ROM_END     = 0x00410000;
RECOMP_SYMBOL uintptr_t MM_rzip_ROM_START   = 0x00500000;
RECOMP_SYMBOL uintptr_t MM_rzip_ROM_END     = 0x00510000;
RECOMP_SYMBOL uintptr_t TTC_rzip_ROM_START  = 0x00600000;
RECOMP_SYMBOL uintptr_t TTC_rzip_ROM_END    = 0x00610000;
RECOMP_SYMBOL uintptr_t CC_rzip_ROM_START   = 0x00700000;
RECOMP_SYMBOL uintptr_t CC_rzip_ROM_END     = 0x00710000;
RECOMP_SYMBOL uintptr_t BGS_rzip_ROM_START  = 0x00800000;
RECOMP_SYMBOL uintptr_t BGS_rzip_ROM_END    = 0x00810000;
RECOMP_SYMBOL uintptr_t FP_rzip_ROM_START   = 0x00900000;
RECOMP_SYMBOL uintptr_t FP_rzip_ROM_END     = 0x00910000;
RECOMP_SYMBOL uintptr_t GV_rzip_ROM_START   = 0x00A00000;
RECOMP_SYMBOL uintptr_t GV_rzip_ROM_END     = 0x00A10000;
RECOMP_SYMBOL uintptr_t MMM_rzip_ROM_START  = 0x00B00000;
RECOMP_SYMBOL uintptr_t MMM_rzip_ROM_END    = 0x00B10000;
RECOMP_SYMBOL uintptr_t RBB_rzip_ROM_START  = 0x00C00000;
RECOMP_SYMBOL uintptr_t RBB_rzip_ROM_END    = 0x00C10000;
RECOMP_SYMBOL uintptr_t CCW_rzip_ROM_START  = 0x00D00000;
RECOMP_SYMBOL uintptr_t CCW_rzip_ROM_END    = 0x00D10000;

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
