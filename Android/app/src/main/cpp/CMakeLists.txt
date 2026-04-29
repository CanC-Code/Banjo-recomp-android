cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# === 1. Verification / Bridge sources (expand as needed) ===
set(BRIDGE_SOURCES
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp
)

# Add more bridge files here once you implement them
# e.g. ultra/math_bridge.cpp, ultra/timer_bridge.cpp, core2/shims.cpp, etc.

# === 2. Game sources with heavy pruning ===
option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # Version filtering (keep only us.v10)
    set(FILES_TO_REMOVE "")
    foreach(FILE_PATH ${GAME_SOURCES})
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                # Also remove the non-versioned variant if it exists
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                list(APPEND FILES_TO_REMOVE ${BASE_FILE})
            endif()
        endif()
    endforeach()

    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
    endif()

    # === Critical: Remove conflicting subsystems ===
    file(GLOB_RECURSE CONFLICTS
        "${REPO_ROOT}/src/core1/*"
        "${REPO_ROOT}/src/done/*"
        # Add more directories that belong to the old emulator/runtime if they cause duplicate symbols
        # "${REPO_ROOT}/src/core2/*"   # ← only if you provide full shims
    )
    if(CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${CONFLICTS})
    endif()

    set(ALL_SOURCES ${BRIDGE_SOURCES} ${GAME_SOURCES})
else()
    set(ALL_SOURCES ${BRIDGE_SOURCES})
endif()

add_library(bkawrapper SHARED ${ALL_SOURCES})

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

target_compile_options(bkawrapper PRIVATE
    "-include${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    -w
    -fpermissive
    -Wno-error=implicit-int
    -Wno-error=int-conversion
    -Wno-error=implicit-function-declaration
    -Wno-error=incompatible-pointer-types
    -Wno-error=unused-function
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
    $<$<COMPILE_LANGUAGE:C>:-std=gnu11>
)

target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    VERSION=0
    # Add these if helpful for stubs:
    # N64_RECOMP
    # __ANDROID__
)

find_library(log-lib log)
target_link_libraries(bkawrapper PRIVATE
    android
    ${log-lib}
    GLESv3
    EGL
    z
)