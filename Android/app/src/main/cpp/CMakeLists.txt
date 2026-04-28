cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# --- 1. Define Core Verification Sources ---
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

# --- 2. Dynamically Include Game Source (The 870 Files) ---
# This matches the -DEXCLUDE_GAME_SRC flag from your workflow
option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "Including game source files from ${REPO_ROOT}/src")
    
    # Recursively find all C files in the game source
    file(GLOB_RECURSE GAME_SOURCES 
        "${REPO_ROOT}/src/*.c"
    )
    
    # Optional: Filter out specific incompatible files if needed
    # list(REMOVE_ITEM GAME_SOURCES "${REPO_ROOT}/src/problematic_file.c")
    
    set(ALL_SOURCES ${VERIFICATION_SOURCES} ${GAME_SOURCES})
else()
    message(STATUS "Building in Verification Mode (Bridge only)")
    set(ALL_SOURCES ${VERIFICATION_SOURCES})
endif()

add_library(bkawrapper SHARED ${ALL_SOURCES})

# --- 3. Include Paths ---
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src               # Essential for internal game headers
    ${REPO_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# --- 4. Realignment Compilation Options ---
# Addressing modern Clang restrictions for legacy MIPS code
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"                           # Silences warnings (useful for initial alignment)
    "-fpermissive"                 # Softens C++ standard checks if any .c is treated as .cpp
    "-Wno-error=implicit-int"      # Common in IDO 5.3 code
    "-Wno-error=int-conversion"    # Critical for 32-bit pointer logic on 64-bit ARM
    "-Wno-error=implicit-function-declaration"
)

# --- 5. Linking ---
find_library(log-lib log)
target_link_libraries(bkawrapper 
    android 
    ${log-lib} 
    GLESv3 
    EGL
    z 
)
