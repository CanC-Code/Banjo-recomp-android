cmake_minimum_required(VERSION 3.22.1)
project(bkawrapper)

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# ============================================================
# 1. Game Source Files (the recompiled N64 C code)
# ============================================================
option(EXCLUDE_GAME_SRC "Skip compiling the recompiled game source tree" OFF)

set(GAME_SOURCES "")
if(NOT EXCLUDE_GAME_SRC)
    file(GLOB_RECURSE GAME_SOURCES
        "${REPO_ROOT}/src/*.c"
    )
    message(STATUS "Game source files found: ${GAME_SOURCES}")
else()
    message(STATUS "EXCLUDE_GAME_SRC=ON: skipping game source tree")
endif()

# ============================================================
# 2. Bridge Sources
# ============================================================
set(BRIDGE_SOURCES
    # Real implementations — must precede missing_stubs.c
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp          
    ultra/exceptasm.cpp          
    ultra/LinkerSymbols.cpp      # NEW: Provides the ROM markers and math constants
    ultra/setintmask.cpp         
    ultra/math_bridge.cpp
    ultra/audio_bridge.cpp
    ultra/lowlevel_bridge.cpp
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp

    # Dead-stub fallbacks — MUST be last
    ultra/missing_stubs.c
)

# ============================================================
# 3. Add Library
# ============================================================
add_library(bkawrapper SHARED
    ${BRIDGE_SOURCES}
    ${GAME_SOURCES}
)

# ============================================================
# 4. Include Directories
# ============================================================
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src
)

# ============================================================
# 5. Compile Options
# ============================================================
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

# ============================================================
# 6. Defines & Linking
# ============================================================
target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    N64_RECOMP
    VERSION=0
    __ANDROID__
)

find_library(log-lib     log)
find_library(android-lib android)
find_library(gles3-lib   GLESv3)
find_library(gles2-lib   GLESv2)
find_library(z-lib       z)

target_link_libraries(bkawrapper
    ${log-lib}
    ${android-lib}
    ${gles3-lib}
    ${gles2-lib}
    ${z-lib}
    atomic
    m
)

target_link_options(bkawrapper PRIVATE "-Wl,--allow-multiple-definition")
