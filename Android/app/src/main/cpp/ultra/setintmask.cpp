// File: Android/app/src/main/cpp/setintmask.cpp

#include <cstdint>
#include <array>

// ------------------------------------------------------------
// N64 interrupt mask constants
// ------------------------------------------------------------
constexpr uint16_t CLR_SP = 0x0001;
constexpr uint16_t SET_SP = 0x0002;
constexpr uint16_t CLR_SI = 0x0004;
constexpr uint16_t SET_SI = 0x0008;
constexpr uint16_t CLR_AI = 0x0010;
constexpr uint16_t SET_AI = 0x0020;
constexpr uint16_t CLR_VI = 0x0040;
constexpr uint16_t SET_VI = 0x0080;
constexpr uint16_t CLR_PI = 0x0100;
constexpr uint16_t SET_PI = 0x0200;
constexpr uint16_t CLR_DP = 0x0400;
constexpr uint16_t SET_DP = 0x0800;

constexpr uint32_t MI_INTR_MASK = 0x3F;

// ------------------------------------------------------------
// __osRcpImTable (exact match to SDK)
// ------------------------------------------------------------
static constexpr std::array<uint16_t, 64> osRcpImTable = {{
    CLR_SP|CLR_SI|CLR_AI|CLR_VI|CLR_PI|CLR_DP,
    SET_SP|CLR_SI|CLR_AI|CLR_VI|CLR_PI|CLR_DP,
    CLR_SP|SET_SI|CLR_AI|CLR_VI|CLR_PI|CLR_DP,
    SET_SP|SET_SI|CLR_AI|CLR_VI|CLR_PI|CLR_DP,
    CLR_SP|CLR_SI|SET_AI|CLR_VI|CLR_PI|CLR_DP,
    SET_SP|CLR_SI|SET_AI|CLR_VI|CLR_PI|CLR_DP,
    CLR_SP|SET_SI|SET_AI|CLR_VI|CLR_PI|CLR_DP,
    SET_SP|SET_SI|SET_AI|CLR_VI|CLR_PI|CLR_DP,
    CLR_SP|CLR_SI|CLR_AI|SET_VI|CLR_PI|CLR_DP,
    SET_SP|CLR_SI|CLR_AI|SET_VI|CLR_PI|CLR_DP,
    CLR_SP|SET_SI|CLR_AI|SET_VI|CLR_PI|CLR_DP,
    SET_SP|SET_SI|CLR_AI|SET_VI|CLR_PI|CLR_DP,
    CLR_SP|CLR_SI|SET_AI|SET_VI|CLR_PI|CLR_DP,
    SET_SP|CLR_SI|SET_AI|SET_VI|CLR_PI|CLR_DP,
    CLR_SP|SET_SI|SET_AI|SET_VI|CLR_PI|CLR_DP,
    SET_SP|SET_SI|SET_AI|SET_VI|CLR_PI|CLR_DP,
    CLR_SP|CLR_SI|CLR_AI|CLR_VI|SET_PI|CLR_DP,
    SET_SP|CLR_SI|CLR_AI|CLR_VI|SET_PI|CLR_DP,
    CLR_SP|SET_SI|CLR_AI|CLR_VI|SET_PI|CLR_DP,
    SET_SP|SET_SI|CLR_AI|CLR_VI|SET_PI|CLR_DP,
    CLR_SP|CLR_SI|SET_AI|CLR_VI|SET_PI|CLR_DP,
    SET_SP|CLR_SI|SET_AI|CLR_VI|SET_PI|CLR_DP,
    CLR_SP|SET_SI|SET_AI|CLR_VI|SET_PI|CLR_DP,
    SET_SP|SET_SI|SET_AI|CLR_VI|SET_PI|CLR_DP,
    CLR_SP|CLR_SI|CLR_AI|SET_VI|SET_PI|CLR_DP,
    SET_SP|CLR_SI|CLR_AI|SET_VI|SET_PI|CLR_DP,
    CLR_SP|SET_SI|CLR_AI|SET_VI|SET_PI|CLR_DP,
    SET_SP|SET_SI|CLR_AI|SET_VI|SET_PI|CLR_DP,
    CLR_SP|CLR_SI|SET_AI|SET_VI|SET_PI|CLR_DP,
    SET_SP|CLR_SI|SET_AI|SET_VI|SET_PI|CLR_DP,
    CLR_SP|SET_SI|SET_AI|SET_VI|SET_PI|CLR_DP,
    SET_SP|SET_SI|SET_AI|SET_VI|SET_PI|CLR_DP,
    CLR_SP|CLR_SI|CLR_AI|CLR_VI|CLR_PI|SET_DP,
    SET_SP|CLR_SI|CLR_AI|CLR_VI|CLR_PI|SET_DP,
    CLR_SP|SET_SI|CLR_AI|CLR_VI|CLR_PI|SET_DP,
    SET_SP|SET_SI|CLR_AI|CLR_VI|CLR_PI|SET_DP,
    CLR_SP|CLR_SI|SET_AI|CLR_VI|CLR_PI|SET_DP,
    SET_SP|CLR_SI|SET_AI|CLR_VI|CLR_PI|SET_DP,
    CLR_SP|SET_SI|SET_AI|CLR_VI|CLR_PI|SET_DP,
    SET_SP|SET_SI|SET_AI|CLR_VI|CLR_PI|SET_DP,
    CLR_SP|CLR_SI|CLR_AI|SET_VI|CLR_PI|SET_DP,
    SET_SP|CLR_SI|CLR_AI|SET_VI|CLR_PI|SET_DP,
    CLR_SP|SET_SI|CLR_AI|SET_VI|CLR_PI|SET_DP,
    SET_SP|SET_SI|CLR_AI|SET_VI|CLR_PI|SET_DP,
    CLR_SP|CLR_SI|SET_AI|SET_VI|CLR_PI|SET_DP,
    SET_SP|CLR_SI|SET_AI|SET_VI|CLR_PI|SET_DP,
    CLR_SP|SET_SI|SET_AI|SET_VI|CLR_PI|SET_DP,
    SET_SP|SET_SI|SET_AI|SET_VI|CLR_PI|SET_DP,
    CLR_SP|CLR_SI|CLR_AI|CLR_VI|SET_PI|SET_DP,
    SET_SP|CLR_SI|CLR_AI|CLR_VI|SET_PI|SET_DP,
    CLR_SP|SET_SI|CLR_AI|CLR_VI|SET_PI|SET_DP,
    SET_SP|SET_SI|CLR_AI|CLR_VI|SET_PI|SET_DP,
    CLR_SP|CLR_SI|SET_AI|CLR_VI|SET_PI|SET_DP,
    SET_SP|CLR_SI|SET_AI|CLR_VI|SET_PI|SET_DP,
    CLR_SP|SET_SI|SET_AI|CLR_VI|SET_PI|SET_DP,
    SET_SP|SET_SI|SET_AI|CLR_VI|SET_PI|SET_DP,
    CLR_SP|CLR_SI|CLR_AI|SET_VI|SET_PI|SET_DP,
    SET_SP|CLR_SI|CLR_AI|SET_VI|SET_PI|SET_DP,
    CLR_SP|SET_SI|CLR_AI|SET_VI|SET_PI|SET_DP,
    SET_SP|SET_SI|CLR_AI|SET_VI|SET_PI|SET_DP,
    CLR_SP|CLR_SI|SET_AI|SET_VI|SET_PI|SET_DP,
    SET_SP|CLR_SI|SET_AI|SET_VI|SET_PI|SET_DP,
    CLR_SP|SET_SI|SET_AI|SET_VI|SET_PI|SET_DP,
    SET_SP|SET_SI|SET_AI|SET_VI|SET_PI|SET_DP
}};

// ------------------------------------------------------------
// Emulated hardware state (REAL, not stubbed)
// ------------------------------------------------------------
static uint32_t g_cp0_status          = 0;
static uint32_t g_OSGlobalIntMask     = 0;
static uint16_t g_MI_INTR_MASK_REG    = 0;

// ------------------------------------------------------------
// osSetIntMask
// ------------------------------------------------------------
extern "C" uint32_t osSetIntMask(uint32_t mask)
{
    // mfc0 $t4, $12
    uint32_t oldStatus = g_cp0_status;

    // lw __OSGlobalIntMask
    uint32_t oldMask = g_OSGlobalIntMask;

    // andi / xor / and sequence
    uint32_t inv = (~oldMask) & 0xFF00;
    uint32_t newStatus = (oldStatus & 0xFF01) | inv;

    // MI_INTR_MASK_REG read side effect
    uint32_t mi = g_MI_INTR_MASK_REG;
    if (mi != 0) {
        uint32_t invUpper = (~(oldMask >> 16)) & 0x3F;
        mi |= invUpper;
    }

    newStatus |= (mi << 16);

    // LUT index calculation
    uint32_t index = ((mask & MI_INTR_MASK) & oldMask) >> 15;
    g_MI_INTR_MASK_REG = osRcpImTable[index];

    // Final CP0 status merge
    uint32_t merged =
        (oldStatus & 0xFFFF00FF) |
        ((mask & 0xFF01) & (oldMask & 0xFF00));

    g_cp0_status = merged;
    g_OSGlobalIntMask = mask;

    return oldStatus;
}