cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# --- Project Configuration ---
set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10") # Explicitly targeting US Version 1.0

# --- 1. Define Native Port Infrastructure ---
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

    # Recursively find all C files
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # --- Version and Library Selection ---
    set(FILES_TO_REMOVE "")

    foreach(FILE_PATH ${GAME_SOURCES})
        # Check if the file is a versioned variant (us, pal, jp, v10, v11)
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            # If it's NOT our target version, discard it
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                # If it IS our target version, remove the "generic" base file
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                list(APPEND FILES_TO_REMOVE ${BASE_FILE})
            endif()
        endif()
    endforeach()

    # Remove versioned files and their base counterparts
    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
        message(STATUS "Version Selector: Active for ${TARGET_VERSION}")
    endif()

    # --- Bridge Subsystem Conflicts ---
    file(GLOB_RECURSE BRIDGE_CONFLICTS
        "${REPO_ROOT}/src/core1/os/*.c"
        "${REPO_ROOT}/src/core1/io/*.c"
        "${REPO_ROOT}/src/core1/audio/sl*.c"
        "${REPO_ROOT}/src/core1/inflate.c"
        "${REPO_ROOT}/src/core1/code_0*.c"
        "${REPO_ROOT}/src/core1/code_7F60*.c"
    )

    if(BRIDGE_CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${BRIDGE_CONFLICTS})
        message(STATUS "Subsystem Pruning: Removed OS/Audio/Decompression collisions.")
    endif()

    # Combine all sources
    set(ALL_SOURCES ${VERIFICATION_SOURCES} ${GAME_SOURCES})
endif()

# --- 3. Create the Library ---
add_library(bkawrapper SHARED ${ALL_SOURCES})

# --- 4. Include Paths ---
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

# --- 5. Compilation Flags ---
# Global flags for both C and C++
target_compile_options(bkawrapper PRIVATE
    "-include${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"
    "-fpermissive"
    "-Wno-error=implicit-int"
    "-Wno-error=int-conversion"
    "-Wno-error=implicit-function-declaration"
    "-Wno-error=incompatible-pointer-types"
)

# C++-only flags (e.g., -std=c++17)
target_compile_options(bkawrapper PRIVATE
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
)

# C-only flags (e.g., -std=gnu11)
target_compile_options(bkawrapper PRIVATE
    $<$<COMPILE_LANGUAGE:C>:-std=gnu11>
)

# --- 6. Compile Definitions ---
target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    VERSION=0 # Target us.v10
)

# --- 7. Linking ---
find_library(log-lib log)
if(NOT log-lib)
    message(FATAL_ERROR "Required library 'log' not found.")
endif()

target_link_libraries(bkawrapper PRIVATE
    android
    ${log-lib}
    GLESv3
    EGL
    z
)