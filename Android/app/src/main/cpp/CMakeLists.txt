cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# Path Setup
set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(GAME_SRC ${REPO_ROOT}/src)
set(GAME_INC ${REPO_ROOT}/include)

# Source Discovery
file(GLOB_RECURSE EMULATOR_SRC "emulator/*.cpp")
file(GLOB_RECURSE ULTRA_SRC "ultra/*.cpp")
file(GLOB_RECURSE TOOLS_SRC "tools/*.cpp")
file(GLOB_RECURSE MENU_SRC "menu/*.cpp")
file(GLOB_RECURSE GAME_CORE "${GAME_SRC}/*.c")

add_library(bkawrapper SHARED 
    ${EMULATOR_SRC} 
    ${ULTRA_SRC} 
    ${TOOLS_SRC} 
    ${MENU_SRC}
    ${GAME_CORE}
)

# CRITICAL: Bridge folders must come FIRST
# This ensures "n64_types.h" in your local folder is found before 
# any potentially conflicting system headers.
target_include_directories(bkawrapper PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${GAME_INC}
    ${GAME_INC}/2.0L
    ${GAME_INC}/2.0L/PR
)

target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    -w          # Suppress legacy warnings
    -fcommon    # Allow multiple definitions of global variables (common in old C)
    -O2         # Optimization level
    -fno-strict-aliasing # Crucial for N64 type-punned pointer logic
)

target_link_libraries(bkawrapper 
    android 
    log 
    GLESv3 
    EGL
)
