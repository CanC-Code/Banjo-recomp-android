#include <cstdint>

// Macro collision fix: Undefine N64 hardware names so we can use them as symbols
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

#define RECOMP_SYMBOL __attribute__((used)) __attribute__((visibility("default")))

extern "C" {

/**
 * 1. Hardware Register Mappings
 * We map the N64 register offsets to our safe buffer in NativeBridge.cpp.
 */
extern uint32_t* gN64_Reg_Base;

// RI (RAM Interface) 
RECOMP_SYMBOL uint32_t* RI_CONFIG_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x00);
RECOMP_SYMBOL uint32_t* RI_CURRENT_LOAD_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x04);
RECOMP_SYMBOL uint32_t* RI_SELECT_REG       = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x08);
RECOMP_SYMBOL uint32_t* RI_REFRESH_REG      = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x10);

// VI (Video Interface) - Faulted at 0xA4400010
// We map these starting at offset 0x1000 in our dummy buffer
RECOMP_SYMBOL uint32_t* VI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1000);
RECOMP_SYMBOL uint32_t* VI_ORIGIN_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1004);
RECOMP_SYMBOL uint32_t* VI_WIDTH_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1008);
RECOMP_SYMBOL uint32_t* VI_V_INTR_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x100C);
RECOMP_SYMBOL uint32_t* VI_V_CURRENT_LINE_REG = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1010);
RECOMP_SYMBOL uint32_t* VI_BURST_REG          = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1014);
RECOMP_SYMBOL uint32_t* VI_V_SYNC_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1018); // Map to the crash address
RECOMP_SYMBOL uint32_t* VI_H_SYNC_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x101C);
RECOMP_SYMBOL uint32_t* VI_LEAP_REG           = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1020);
RECOMP_SYMBOL uint32_t* VI_H_START_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1024);
RECOMP_SYMBOL uint32_t* VI_V_START_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1028);
RECOMP_SYMBOL uint32_t* VI_V_BURST_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x102C);
RECOMP_SYMBOL uint32_t* VI_X_SCALE_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1030);
RECOMP_SYMBOL uint32_t* VI_Y_SCALE_REG        = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x1034);

// PI (Peripheral Interface)
RECOMP_SYMBOL uint32_t* PI_STATUS_REG         = (uint32_t*)((uintptr_t)gN64_Reg_Base + 0x2000);

/**
 * 2. Math & Markers
 */
RECOMP_SYMBOL uint32_t __libm_qnan_f = 0x7FC00000;
RECOMP_SYMBOL uintptr_t core1_VRAM           = 0x80001000; 
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_START = 0x00001050;
RECOMP_SYMBOL uintptr_t core1_rzip_ROM_END   = 0x000E0000;
RECOMP_SYMBOL uintptr_t core2_rzip_ROM_START = 0x000F0000;
RECOMP_SYMBOL uintptr_t core2_rzip_ROM_END   = 0x001F0000;
RECOMP_SYMBOL uintptr_t gOverlayTable = 0x01200000;

// (Keep your existing level rzip markers here...)

} // extern "C"
