// File: Android/app/src/main/cpp/ultra/libm_vals.cpp
#include <cstdint>

extern "C" {

// Single-precision quiet NaN (matching 0x7F810000)
alignas(4) const uint32_t __libm_qnan_f = 0x7F810000;

} // extern "C"