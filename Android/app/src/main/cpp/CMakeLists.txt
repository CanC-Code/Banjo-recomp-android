cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Define Paths (Game code is now at the REPO root)
set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(GAME_SRC ${REPO_ROOT}/src)
set(GAME_INC ${REPO_ROOT}/include)

# 2. Gather all Source Files
file(GLOB_RECURSE EMULATOR_SRC "emulator/*.cpp")
file(GLOB_RECURSE ULTRA_SRC "ultra/*.cpp")
file(GLOB_RECURSE TOOLS_SRC "tools/*.cpp")
file(GLOB_RECURSE MENU_SRC "menu/*.cpp")
# Include original game C files (Targeted core files only)
file(GLOB_RECURSE GAME_CORE "${GAME_SRC}/*.c")

add_library(bkawrapper SHARED 
    ${EMULATOR_SRC} 
    ${ULTRA_SRC} 
    ${TOOLS_SRC} 
    ${MENU_SRC}
    ${GAME_CORE}
)

# 3. Setup Include Paths
# CRITICAL: Local Android bridge folders MUST be listed first. 
# This ensures that when the compiler looks for "n64_types.h" or 
# standard headers, it doesn't get diverted into the legacy /include folder.
target_include_directories(bkawrapper PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${GAME_INC}
    ${GAME_INC}/2.0L
    ${GAME_INC}/2.0L/PR
)

# 4. Apply the Zero-Touch Porting Flag
# "-include" forces n64_types.h to be injected into every file automatically.
# -fcommon handles the N64 engine's use of global variable redefinitions.
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    -w 
    -fcommon 
    -O2 
    -fno-strict-aliasing
)

target_link_libraries(bkawrapper android log GLESv3 EGL)
