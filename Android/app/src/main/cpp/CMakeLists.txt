cmake_minimum_required(VERSION 3.22.1)
project(bkawrapper)

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# ============================================================
# 1. Bridge Sources (CORE RUNTIME LAYER)
# ============================================================
set(BRIDGE_SOURCES
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp
    ultra/math_bridge.cpp
    ultra/audio_bridge.cpp
    ultra/lowlevel_bridge.cpp
    ultra/missing_stubs.c
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp
)

# ============================================================
# 2. Add Library
# ============================================================
add_library(bkawrapper SHARED
    ${BRIDGE_SOURCES}
    # Note: Game sources are usually added here via a separate glob or script
)

# ============================================================
# 3. Include Directories
# ============================================================
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src
)

# ============================================================
# 4. Compile Options
# ============================================================

target_compile_options(bkawrapper PRIVATE
    # CRITICAL: This injects n64_types.h into every source file automatically
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
# 5. Defines & Linking
# ============================================================
target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    N64_RECOMP
    VERSION=0
    __ANDROID__
)

find_library(log-lib log)
target_link_libraries(bkawrapper ${log-lib})
target_link_options(bkawrapper PRIVATE "-Wl,--allow-multiple-definition")
