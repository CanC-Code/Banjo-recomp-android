// File: Android/app/src/main/cpp/ultra/parameters.cpp
#include <cstdint>

extern "C" {

// N64 OS parameters
// These must match the declarations in the N64 SDK headers (os_system.h, etc.)
uint32_t leoBootID       = 0;
int32_t  osTvType        = 0;       // SDK expects s32
int32_t  osRomType       = 0;       // SDK expects s32
void* osRomBase       = nullptr; // SDK expects void* (64-bit pointer on Android)
int32_t  osResetType     = 0;       // SDK expects s32
int32_t  osCicId         = 0;       // SDK expects s32
int32_t  osVersion       = 0;       // SDK expects s32
uint32_t osMemSize       = 0;

// The SDK declares this as 'extern s32 osAppNMIBuffer[];'
// We define it as an array of 16 integers (a standard N64 size).
int32_t  osAppNMIBuffer[16] = {0};

// Padding to match the original .space 0x60 in assembly
alignas(0x4) uint8_t __parameters_pad[0x60] = {0};

} // extern "C"
