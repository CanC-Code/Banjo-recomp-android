cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# 1. Define sources
set(VERIFICATION_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"
    "emulator/pi_hle.cpp"
    "emulator/resource_mgr.cpp"
    "tools/rare_decompression.cpp" 
)

add_library(bkawrapper SHARED ${VERIFICATION_SOURCES})

# 2. Include Paths
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# 3. Compilation Options
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"
)

# 4. Linking
find_library(log-lib log)
target_link_libraries(bkawrapper 
    android 
    ${log-lib} 
    GLESv3 
    EGL
    z         # <--- LINK ZLIB HERE to fix 'inflate' errors
)
