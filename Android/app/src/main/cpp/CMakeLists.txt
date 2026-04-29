cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# --- Project Configuration ---
set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# --- 1. Define Native Port Infrastructure ---
set(VERIFICATION_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"      # Must define ALL audio stubs (alLink, alEvtqNew, etc.)
    "emulator/pi_hle.cpp"     # Replaces pirawdma.c
    "emulator/resource_mgr.cpp"
    "tools/rare_decompression.cpp"
)

# --- 2. Original N64 Source Integration ---
option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "Including original N64 source files from ${REPO_ROOT}/src")
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # --- Version and Library Selection ---
    set(FILES_TO_REMOVE "")
    foreach(FILE_PATH ${GAME_SOURCES})
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                list(APPEND FILES_TO_REMOVE ${BASE_FILE})
            endif()
        endif()
    endforeach()
    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
        message(STATUS "Version Selector: Active for ${TARGET_VERSION}")
    endif()

    # --- Bridge Subsystem Conflicts ---
    # Exclude ALL files that conflict with the bridge or stubs
    set(BRIDGE_CONFLICTS
        "${REPO_ROOT}/src/core1/os/*.c"
        "${REPO_ROOT}/src/core1/io/*.c"
        "${REPO_ROOT}/src/core1/audio/sl*.c"
        "${REPO_ROOT}/src/core1/audio/event.c"  # Conflicts with stubs.cpp
        "${REPO_ROOT}/src/core1/audio/seq.c"     # Conflicts with stubs.cpp
        "${REPO_ROOT}/src/core1/audio/synth.c"   # Conflicts with stubs.cpp
        "${REPO_ROOT}/src/core1/inflate.c"       # Handled by rare_decompression.cpp
        "${REPO_ROOT}/src/core1/code_0*.c"       # Entry point clash
        "${REPO_ROOT}/src/core1/code_7F60*.c"    # Math library duplicates
        "${REPO_ROOT}/src/done/pirawdma.c"       # Conflicts with pi_hle.cpp
        "${REPO_ROOT}/src/done/ll.c"             # Conflicts with bridge
    )
    if(BRIDGE_CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${BRIDGE_CONFLICTS})
        message(STATUS "Subsystem Pruning: Removed OS/Audio/Decompression collisions, pirawdma.c, and ll.c.")
    endif()

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
target_compile_options(bkawrapper PRIVATE
    "-include${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"
    "-fpermissive"
    "-Wno-error=implicit-int"
    "-Wno-error=int-conversion"
    "-Wno-error=implicit-function-declaration"
    "-Wno-error=incompatible-pointer-types"
)
# C++-only flags
target_compile_options(bkawrapper PRIVATE
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
)
# C-only flags
target_compile_options(bkawrapper PRIVATE
    $<$<COMPILE_LANGUAGE:C>:-std=gnu11>
)

# --- 6. Compile Definitions ---
target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    VERSION=0
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