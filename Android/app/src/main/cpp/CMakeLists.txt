cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(GAME_SRC ${REPO_ROOT}/src)
set(GAME_INC ${REPO_ROOT}/include)

# Discover core Android-wrapper files (Always included for OTR functionality)
file(GLOB_RECURSE EMULATOR_SRC "emulator/*.cpp")
file(GLOB_RECURSE ULTRA_SRC "ultra/*.cpp")
file(GLOB_RECURSE TOOLS_SRC "tools/*.cpp")
file(GLOB_RECURSE MENU_SRC "menu/*.cpp")

# --- Conditional Logic for N64 Game Source ---
option(EXCLUDE_GAME_SRC "Exclude N64 source for verification builds" OFF)

if(NOT EXCLUDE_GAME_SRC)
    file(GLOB_RECURSE GAME_CORE "${GAME_SRC}/*.c")
    message(STATUS "Including Game Source files")
else()
    set(GAME_CORE "")
    add_definitions(-DNO_GAME_SRC) # Used to stub calls in NativeBridge.cpp
    message(STATUS "Excluding Game Source - Verification Mode")
endif()

add_library(bkawrapper SHARED
    ${EMULATOR_SRC}
    ${ULTRA_SRC}
    ${TOOLS_SRC}
    ${MENU_SRC}
    ${GAME_CORE}
)

target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${GAME_INC}
    ${GAME_INC}/2.0L
    ${GAME_INC}/2.0L/PR
)

add_definitions(-DOEPRESCRIPT=1 -DDANDROID02=1)

target_compile_options(bkawrapper PRIVATE
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    -w -fcommon -O2 -fno-strict-aliasing
)

find_library(log-lib log)
find_library(opensl-lib OpenSLES)

target_link_libraries(bkawrapper android ${log-lib} ${opensl-lib} GLESv3 EGL)
