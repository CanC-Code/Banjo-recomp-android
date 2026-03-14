// File: Android/app/src/main/cpp/ultra/parameters.cpp
#include <cstdint>

extern "C" {

// N64 OS parameters (originally at fixed addresses)
uint32_t leoBootID       = 0;
uint32_t osTvType        = 0;
uint32_t osRomType       = 0;
uint32_t osRomBase       = 0;
uint32_t osResetType     = 0;
uint32_t osCicId         = 0;
uint32_t osVersion       = 0;
uint32_t osMemSize       = 0;
uint32_t osAppNMIBuffer  = 0;

// Padding to match the original .space 0x60 in assembly
alignas(0x4) uint8_t __parameters_pad[0x60] = {0};

} // extern "C"