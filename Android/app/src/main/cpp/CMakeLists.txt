cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(GAME_SRC ${REPO_ROOT}/src)
set(GAME_INC ${REPO_ROOT}/include)

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

# CRITICAL: Bridge folders must come FIRST to prevent header hijacking
target_include_directories(bkawrapper PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}           # <--- ADDED: Allows resolving #include "tools/..."
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${GAME_INC}
    ${GAME_INC}/2.0L
    ${GAME_INC}/2.0L/PR
)

target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    -w -fcommon -O2 -fno-strict-aliasing
)

target_link_libraries(bkawrapper android log GLESv3 EGL)
