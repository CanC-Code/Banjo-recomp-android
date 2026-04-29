Cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# ============================================================
# 1. Bridge Sources (CORE RUNTIME LAYER)
# ============================================================

set(BRIDGE_SOURCES
    # Core bridge
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp

    # NEW bridges (critical)
    ultra/math_bridge.cpp
    ultra/audio_bridge.cpp
    ultra/lowlevel_bridge.cpp

    # NEW: C-side stubs for linker symbols and hardware calls
    ultra/missing_stubs.c

    # Emulator / runtime
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp

    # Tools
    tools/rare_decompression.cpp
)

# ============================================================
# 2. Game Sources (Heavily Filtered)
# ============================================================

option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # --- Keep ONLY us.v10 ---
    set(FILES_TO_REMOVE "")
    foreach(FILE_PATH ${GAME_SOURCES})
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            if(NOT ${FILE_PATH} MATCHES ".*\\.us\\.v10\\.c$")
                list(APPEND FILES_TO_REMOVE ${FILE_PATH})
            else()
                # Remove duplicate non-versioned file
                string(REGEX REPLACE "\\.us\\.v10\\.c$" ".c" BASE_FILE ${FILE_PATH})
                list(APPEND FILES_TO_REMOVE ${BASE_FILE})
            endif()
        endif()
    endforeach()

    if(FILES_TO_REMOVE)
        list(REMOVE_ITEM GAME_SOURCES ${FILES_TO_REMOVE})
    endif()

    # --- Remove conflicting subsystems ---
    file(GLOB_RECURSE CONFLICTS
        "${REPO_ROOT}/src/done/*"
    )

    # FIX: Rescue bk_boot_1050.c from the conflicts list so bootproc is compiled!
    if(CONFLICTS)
        list(REMOVE_ITEM CONFLICTS "${REPO_ROOT}/src/done/bk_boot_1050.c")
        list(REMOVE_ITEM GAME_SOURCES ${CONFLICTS})
    endif()

    set(ALL_SOURCES ${BRIDGE_SOURCES} ${GAME_SOURCES})
else()
    set(ALL_SOURCES ${BRIDGE_SOURCES})
endif()

# ============================================================
# 3. Library
# ============================================================

add_library(bkawrapper SHARED ${ALL_SOURCES})

# ============================================================
# 4. Includes
# ============================================================

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

# ============================================================
# 5. Compile Options
# ============================================================

target_compile_options(bkawrapper PRIVATE
    "-include${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"

    -w
    -fpermissive

    # Relax legacy code issues
    -Wno-error=implicit-int
    -Wno-error=int-conversion
    -Wno-error=implicit-function-declaration
    -Wno-error=incompatible-pointer-types
    -Wno-error=unused-function

    # Language standards
    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
    $<$<COMPILE_LANGUAGE:C>:-std=gnu11>
)

# ============================================================
# 6. Defines
# ============================================================

target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    VERSION=0
    N64_RECOMP
    __ANDROID__
)

# ============================================================
# 7. Link Options & Libraries
# ============================================================

find_library(log-lib log)

# Allows Android Bridges to override N64 functions
target_link_options(bkawrapper PRIVATE "-Wl,--allow-multiple-definition")

target_link_libraries(bkawrapper PRIVATE
    android
    ${log-lib}
    GLESv3
    EGL
    z
    atomic
    m
)
