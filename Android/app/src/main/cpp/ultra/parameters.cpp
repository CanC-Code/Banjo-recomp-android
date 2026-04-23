#include <cstdint>

extern "C" {

/**
 * N64 OS parameters
 * These variables were originally located at fixed memory addresses on the N64.
 * We define them here so the recompiled code and the HLE (High Level Emulation)
 * functions can access them.
 */

// Boot ID used by the 64DD (if applicable)
uint32_t leoBootID       = 0;

// TV System: 0 = PAL, 1 = NTSC, 2 = MPAL
int32_t  osTvType        = 0;

// Type of ROM: 0 = Cartridge, 1 = Bulk
int32_t  osRomType       = 0;

// Pointer to the base address of the game image in memory
void* osRomBase       = nullptr;

// Type of reset: 0 = Cold Reset, 1 = NMI (Reset Button)
int32_t  osResetType     = 0;

// The ID of the CIC security chip on the cartridge
int32_t  osCicId         = 0;

// OS Version Number
int32_t  osVersion       = 0;

// Total amount of available memory (RDRAM)
uint32_t osMemSize       = 0;

// Buffer used during a Non-Maskable Interrupt (Reset)
// The SDK expects an array of signed 32-bit integers.
int32_t  osAppNMIBuffer[16] = {0};

/**
 * Memory Layout Padding
 * This mimics the '.space 0x60' found in original MIPS assembly to ensure
 * that any variables following this block are correctly offset.
 */
alignas(0x4) uint8_t __parameters_pad[0x60] = {0};

} // extern "C"
