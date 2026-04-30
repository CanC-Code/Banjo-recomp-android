#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Basic typedefs (safe fallback)
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t  u8;

// Stub register interface
u32 ReadHardwareRegister(u32 addr);
void WriteHardwareRegister(u32 addr, u32 value);

// Optional: initialization hook
void InitHardwareRegs(void);

#ifdef __cplusplus
}
#endif