cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# Define specific sources to build for verification
# We EXCLUDE exceptasm.cpp and audio_helper.cpp because they are too complex to stub
set(VERIFICATION_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"
    "emulator/pi_hle.cpp"
    "emulator/resource_mgr.cpp"
)

add_library(bkawrapper SHARED ${VERIFICATION_SOURCES})

# Include Paths
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/include/2.0L/PR
    # Path to rare_decompression.h (Adjust if your folder name is different)
    ${REPO_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# Force-include our types header
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w" # Suppress warnings to focus on errors
)

find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL)
