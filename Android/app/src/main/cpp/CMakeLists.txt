cmake_minimum_required(VERSION 3.22.1)
project(bkawrapper)

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# ============================================================
# 1. Game Source Files (the recompiled N64 C code)
#    Controlled by -DEXCLUDE_GAME_SRC=ON/OFF
#    Default OFF so the full game compiles unless explicitly skipped.
# ============================================================
option(EXCLUDE_GAME_SRC "Skip compiling the recompiled game source tree" OFF)

set(GAME_SOURCES "")
if(NOT EXCLUDE_GAME_SRC)
    # Collect every .c file under /src recursively
    file(GLOB_RECURSE GAME_SOURCES
        "${REPO_ROOT}/src/*.c"
    )
    message(STATUS "Game source files found: ${GAME_SOURCES}")
else()
    message(STATUS "EXCLUDE_GAME_SRC=ON: skipping game source tree")
endif()

# ============================================================
# 2. Bridge Sources
#    IMPORTANT: exceptasm, setintmask, libm_vals must come BEFORE
#    missing_stubs.c so the real implementations win under
#    --allow-multiple-definition. missing_stubs.c is last-resort.
# ============================================================
set(BRIDGE_SOURCES
    # Real implementations — must precede missing_stubs.c
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp          # defines __libm_qnan_f (real)
    ultra/exceptasm.cpp          # defines initInterruptTables, __osPopThread, etc (real)
    ultra/setintmask.cpp         # defines osSetIntMask (real)
    ultra/math_bridge.cpp
    ultra/audio_bridge.cpp
    ultra/lowlevel_bridge.cpp
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp

    # Dead-stub fallbacks — MUST be last so real impls above win
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

# System libraries
find_library(log-lib     log)
find_library(android-lib android)   # AAssetManager
find_library(gles3-lib   GLESv3)    # OpenGL ES 3 — NativeBridge.cpp uses GLES3 headers
find_library(gles2-lib   GLESv2)    # Fallback / EGL compatibility
find_library(z-lib       z)         # zlib for rare_decompression

target_link_libraries(bkawrapper
    ${log-lib}
    ${android-lib}
    ${gles3-lib}
    ${gles2-lib}
    ${z-lib}
    atomic
    m
)

# --allow-multiple-definition lets missing_stubs.c coexist with real impls.
# The real impls win because they are listed first above.
target_link_options(bkawrapper PRIVATE "-Wl,--allow-multiple-definition")
