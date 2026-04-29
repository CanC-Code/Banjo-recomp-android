cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# --- 1. Define Native Port Infrastructure ---
# These files are necessary to bridge the N64 logic to Android hardware.
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

# --- 2. Original N64 Source Integration ---
option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "Including original N64 source files from ${REPO_ROOT}/src")

    # Recursively find all C files in the game source (the 870+ files)
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # --- THE CRITICAL FIX: PRUNING DUPLICATES ---
    # We must exclude the recompiled versions of the OS and IO subsystems.
    # Why? Because your Native Bridge (NativeBridge.cpp, pi_hle.cpp, etc.) 
    # already provides modern C++ versions of these functions.
    file(GLOB_RECURSE CONFLICTING_FILES 
        "${REPO_ROOT}/src/done/*.c"      # Manual overrides from previous attempts
        "${REPO_ROOT}/src/core1/os/*.c"  # Original N64 OS logic (conflicts with NativeBridge/stubs)
        "${REPO_ROOT}/src/core1/io/*.c"  # Original N64 IO logic (conflicts with pi_hle.cpp)
    )
    
    if(CONFLICTING_FILES)
        list(REMOVE_ITEM GAME_SOURCES ${CONFLICTING_FILES})
        message(STATUS "Excluded conflicting System/IO folders to prioritize Native Bridge.")
    endif()

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
    ${REPO_ROOT}/src               
    ${REPO_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# --- 4. Compilation Flags for Legacy Code ---
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"                           # Suppress warnings from legacy IDO code
    "-fpermissive"                 
    "-Wno-error=implicit-int"      
    "-Wno-error=int-conversion"    
    "-Wno-error=implicit-function-declaration"
    "-Wno-error=incompatible-pointer-types"
)

# Define the microcode for the Graphics Binary Interface
target_compile_definitions(bkawrapper PRIVATE F3DEX_GBI)

# --- 5. Linking Native Libraries ---
find_library(log-lib log)
target_link_libraries(bkawrapper 
    android 
    ${log-lib} 
    GLESv3 
    EGL
    z 
)
