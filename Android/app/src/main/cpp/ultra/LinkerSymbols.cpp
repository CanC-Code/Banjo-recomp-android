#include <cstdint>

// ============================================================
// 1. MACRO COLLISION FIX
// ============================================================

// RI
#undef RI_CONFIG_REG
#undef RI_CURRENT_LOAD_REG
#undef RI_SELECT_REG
#undef RI_REFRESH_REG

// VI
#undef VI_STATUS_REG
#undef VI_ORIGIN_REG
#undef VI_WIDTH_REG
#undef VI_V_INTR_REG
#undef VI_V_CURRENT_LINE_REG
#undef VI_BURST_REG
#undef VI_V_SYNC_REG
#undef VI_H_SYNC_REG
#undef VI_LEAP_REG
#undef VI_H_START_REG
#undef VI_V_START_REG
#undef VI_V_BURST_REG
#undef VI_X_SCALE_REG
#undef VI_Y_SCALE_REG

// PI
#undef PI_STATUS_REG

// SI (NEW — REQUIRED)
#undef SI_DRAM_ADDR_REG
#undef SI_PIF_ADDR_RD64B_REG
#undef SI_PIF_ADDR_WR64B_REG
#undef SI_STATUS_REG

#define RECOMP_SYMBOL __attribute__((used)) __attribute__((visibility("default")))

extern "C" {

/**
 * 2. HARDWARE REGISTER TRAP
 */
extern uint32_t* gN64_Reg_Base;

// ============================================================
// RI (RAM Interface)
// ============================================================
RECOMP_SYMBOL uint32_t* RI_CONFIG_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x0000);
RECOMP_SYMBOL uint32_t* RI_CURRENT_LOAD_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x0004);
RECOMP_SYMBOL uint32_t* RI_SELECT_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x0008);
RECOMP_SYMBOL uint32_t* RI_REFRESH_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x0010);

// ============================================================
// VI (Video Interface)
// ============================================================
RECOMP_SYMBOL uint32_t* VI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1000);
RECOMP_SYMBOL uint32_t* VI_ORIGIN_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1004);
RECOMP_SYMBOL uint32_t* VI_WIDTH_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1008);
RECOMP_SYMBOL uint32_t* VI_V_INTR_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x100C);
RECOMP_SYMBOL uint32_t* VI_V_CURRENT_LINE_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1010);
RECOMP_SYMBOL uint32_t* VI_BURST_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1014);
RECOMP_SYMBOL uint32_t* VI_V_SYNC_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1018);
RECOMP_SYMBOL uint32_t* VI_H_SYNC_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x101C);
RECOMP_SYMBOL uint32_t* VI_LEAP_REG           = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1020);
RECOMP_SYMBOL uint32_t* VI_H_START_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1024);
RECOMP_SYMBOL uint32_t* VI_V_START_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1028);
RECOMP_SYMBOL uint32_t* VI_V_BURST_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x102C);
RECOMP_SYMBOL uint32_t* VI_X_SCALE_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1030);
RECOMP_SYMBOL uint32_t* VI_Y_SCALE_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1034);

// ============================================================
// PI (Peripheral Interface)
// ============================================================
RECOMP_SYMBOL uint32_t* PI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x2000);

// ============================================================
// SI (Serial Interface)  ← THIS FIXES YOUR CURRENT CRASH
// ============================================================
RECOMP_SYMBOL uint32_t* SI_DRAM_ADDR_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x3000);
RECOMP_SYMBOL uint32_t* SI_PIF_ADDR_RD64B_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x3004);
RECOMP_SYMBOL uint32_t* SI_PIF_ADDR_WR64B_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x3008);
RECOMP_SYMBOL uint32_t* SI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x300C);

// ============================================================
// 3. MATH & ENGINE GLOBALS
// ============================================================
RECOMP_SYMBOL uint32_t __libm_qnan_f = 0x7FC00000;

RECOMP_SYMBOL uintptr_t core1_VRAM           = 0x80001000; 
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_START = 0x00001050;
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_END   = 0x000E0000;

RECOMP_SYMBOL uintptr_t core2_rzip_ROM_START = 0x000F0000;
RECOMP_SYMBOL uintptr_t core2_rzip_ROM_END   = 0x001F0000;

// ============================================================
// 4. LEVEL ROM MARKERS
// ============================================================
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