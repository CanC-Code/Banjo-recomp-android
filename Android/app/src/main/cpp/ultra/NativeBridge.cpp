// File: LinkerSymbols.cpp
#include <cstdint>
#include <cstdlib>

// ============================================================
// 1. MACRO COLLISION FIX
// ============================================================

// Clear existing macros to prevent shadowing of our recompiled symbols
#undef RI_CONFIG_REG
#undef RI_CURRENT_LOAD_REG
#undef RI_SELECT_REG
#undef RI_REFRESH_REG

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

#undef PI_STATUS_REG
#undef PI_DRAM_ADDR_REG
#undef PI_CART_ADDR_REG
#undef PI_RD_LEN_REG
#undef PI_WR_LEN_REG

#undef SI_DRAM_ADDR_REG
#undef SI_PIF_ADDR_RD64B_REG
#undef SI_PIF_ADDR_WR64B_REG
#undef SI_STATUS_REG

#undef MI_INIT_MODE_REG
#undef MI_VERSION_REG
#undef MI_INTR_REG
#undef MI_INTR_MASK_REG

#undef SP_DMEM
#undef SP_IMEM
#undef SP_STATUS_REG

#undef AI_DRAM_ADDR_REG
#undef AI_LEN_REG
#undef AI_CONTROL_REG
#undef AI_STATUS_REG

#undef DPC_START_REG
#undef DPC_END_REG
#undef DPC_CURRENT_REG
#undef DPC_STATUS_REG
#undef DPC_CLOCK_REG
#undef DPC_BUFBUSY_REG
#undef DPC_PIPEBUSY_REG
#undef DPC_TMEM_REG

#define RECOMP_SYMBOL __attribute__((used)) __attribute__((visibility("default")))

extern "C" {

/**
 * 2. HARDWARE REGISTER TRAP ALLOCATION
 */
uint32_t* gN64_Reg_Base = nullptr;

// Invoked by NativeBridge.cpp during JNI initialization
void InitN64Registers() {
    if (gN64_Reg_Base == nullptr) {
        // Allocate 1MB of zeroed memory for the hardware registers
        gN64_Reg_Base = (uint32_t*)calloc(1024 * 1024, 1);
    }
}

// ============================================================
// SP (Signal Processor) - Essential for RSP/Task handling
// ============================================================
RECOMP_SYMBOL uint32_t* SP_DMEM              = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x0000);
RECOMP_SYMBOL uint32_t* SP_IMEM              = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1000);
RECOMP_SYMBOL uint32_t* SP_STATUS_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x2000);

// ============================================================
// MI (MIPS Interface) - Handles Interrupts (CRITICAL)
// ============================================================
RECOMP_SYMBOL uint32_t* MI_INIT_MODE_REG     = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x3000);
RECOMP_SYMBOL uint32_t* MI_VERSION_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x3004);
RECOMP_SYMBOL uint32_t* MI_INTR_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x3008);
RECOMP_SYMBOL uint32_t* MI_INTR_MASK_REG     = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x300C);

// ============================================================
// VI (Video Interface)
// ============================================================
RECOMP_SYMBOL uint32_t* VI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4000);
RECOMP_SYMBOL uint32_t* VI_ORIGIN_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4004);
RECOMP_SYMBOL uint32_t* VI_WIDTH_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4008);
RECOMP_SYMBOL uint32_t* VI_V_INTR_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x400C);
RECOMP_SYMBOL uint32_t* VI_V_CURRENT_LINE_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4010);
RECOMP_SYMBOL uint32_t* VI_BURST_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4014);
RECOMP_SYMBOL uint32_t* VI_V_SYNC_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4018);
RECOMP_SYMBOL uint32_t* VI_H_SYNC_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x401C);
RECOMP_SYMBOL uint32_t* VI_LEAP_REG           = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4020);
RECOMP_SYMBOL uint32_t* VI_H_START_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4024);
RECOMP_SYMBOL uint32_t* VI_V_START_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4028);
RECOMP_SYMBOL uint32_t* VI_V_BURST_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x402C);
RECOMP_SYMBOL uint32_t* VI_X_SCALE_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4030);
RECOMP_SYMBOL uint32_t* VI_Y_SCALE_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x4034);

// ============================================================
// AI (Audio Interface) - Essential for Banjo-Kazooie Sound
// ============================================================
RECOMP_SYMBOL uint32_t* AI_DRAM_ADDR_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x5000);
RECOMP_SYMBOL uint32_t* AI_LEN_REG            = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x5004);
RECOMP_SYMBOL uint32_t* AI_CONTROL_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x5008);
RECOMP_SYMBOL uint32_t* AI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x500C);

// ============================================================
// PI (Peripheral Interface)
// ============================================================
RECOMP_SYMBOL uint32_t* PI_DRAM_ADDR_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x6000);
RECOMP_SYMBOL uint32_t* PI_CART_ADDR_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x6004);
RECOMP_SYMBOL uint32_t* PI_RD_LEN_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x6008);
RECOMP_SYMBOL uint32_t* PI_WR_LEN_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x600C);
RECOMP_SYMBOL uint32_t* PI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x6010);

// ============================================================
// RI (RAM Interface)
// ============================================================
RECOMP_SYMBOL uint32_t* RI_CONFIG_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x7000);
RECOMP_SYMBOL uint32_t* RI_CURRENT_LOAD_REG   = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x7004);
RECOMP_SYMBOL uint32_t* RI_SELECT_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x7008);
RECOMP_SYMBOL uint32_t* RI_REFRESH_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x7010);

// ============================================================
// SI (Serial Interface) - Corrected Offsets (Status is 0x18)
// ============================================================
RECOMP_SYMBOL uint32_t* SI_DRAM_ADDR_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x8000);
RECOMP_SYMBOL uint32_t* SI_PIF_ADDR_RD64B_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x8004);
RECOMP_SYMBOL uint32_t* SI_PIF_ADDR_WR64B_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x8010);
RECOMP_SYMBOL uint32_t* SI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x8018);

// ============================================================
// DPC (Display Processor Command) - Essential for Graphics Rendering
// ============================================================
RECOMP_SYMBOL uint32_t* DPC_START_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x9000);
RECOMP_SYMBOL uint32_t* DPC_END_REG           = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x9004);
RECOMP_SYMBOL uint32_t* DPC_CURRENT_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x9008);
RECOMP_SYMBOL uint32_t* DPC_STATUS_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x900C);
RECOMP_SYMBOL uint32_t* DPC_CLOCK_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x9010);
RECOMP_SYMBOL uint32_t* DPC_BUFBUSY_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x9014);
RECOMP_SYMBOL uint32_t* DPC_PIPEBUSY_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x9018);
RECOMP_SYMBOL uint32_t* DPC_TMEM_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x901C);

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
RECOMP_SYMBOL uintptr_t SM_rzip_ROM_START    = 0x00400000;
RECOMP_SYMBOL uintptr_t SM_rzip_ROM_END      = 0x00410000;
RECOMP_SYMBOL uintptr_t MM_rzip_ROM_START    = 0x00500000;
RECOMP_SYMBOL uintptr_t MM_rzip_ROM_END      = 0x00510000;
RECOMP_SYMBOL uintptr_t TTC_rzip_ROM_START   = 0x00600000;
RECOMP_SYMBOL uintptr_t TTC_rzip_ROM_END     = 0x00610000;
RECOMP_SYMBOL uintptr_t CC_rzip_ROM_START    = 0x00700000;
RECOMP_SYMBOL uintptr_t CC_rzip_ROM_END      = 0x00710000;
RECOMP_SYMBOL uintptr_t BGS_rzip_ROM_START   = 0x00800000;
RECOMP_SYMBOL uintptr_t BGS_rzip_ROM_END     = 0x00810000;
RECOMP_SYMBOL uintptr_t FP_rzip_ROM_START    = 0x00900000;
RECOMP_SYMBOL uintptr_t FP_rzip_ROM_END      = 0x00910000;
RECOMP_SYMBOL uintptr_t GV_rzip_ROM_START    = 0x00A00000;
RECOMP_SYMBOL uintptr_t GV_rzip_ROM_END      = 0x00A10000;
RECOMP_SYMBOL uintptr_t MMM_rzip_ROM_START   = 0x00B00000;
RECOMP_SYMBOL uintptr_t MMM_rzip_ROM_END     = 0x00B10000;
RECOMP_SYMBOL uintptr_t RBB_rzip_ROM_START   = 0x00C00000;
RECOMP_SYMBOL uintptr_t RBB_rzip_ROM_END     = 0x00C10000;
RECOMP_SYMBOL uintptr_t CCW_rzip_ROM_START   = 0x00D00000;
RECOMP_SYMBOL uintptr_t CCW_rzip_ROM_END     = 0x00D10000;

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
