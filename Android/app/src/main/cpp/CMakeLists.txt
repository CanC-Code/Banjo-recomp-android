cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(GAME_SRC ${REPO_ROOT}/src)
set(GAME_INC ${REPO_ROOT}/include)

# 1. OTR Essentials (Required for Extraction Verification)
set(OTR_LOGIC
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "tools/rare_decompression.cpp"
)

# 2. Toggle Game Source and System HAL
option(EXCLUDE_GAME_SRC "Exclude N64 source and HAL for verification" OFF)

if(NOT EXCLUDE_GAME_SRC)
    # Full Build: Include everything
    file(GLOB_RECURSE EMULATOR_SRC "emulator/*.cpp")
    file(GLOB_RECURSE ULTRA_SRC "ultra/*.cpp")
    file(GLOB_RECURSE MENU_SRC "menu/*.cpp")
    file(GLOB_RECURSE GAME_CORE "${GAME_SRC}/*.c")
    
    set(ALL_SOURCES ${EMULATOR_SRC} ${ULTRA_SRC} ${MENU_SRC} ${GAME_CORE})
else()
    # Verification Build: Only compile what's needed for the APK to boot and OTR to run
    add_definitions(-DNO_GAME_SRC)
    set(ALL_SOURCES ${OTR_LOGIC} "emulator/stubs.cpp")
    message(STATUS "Verification Mode: Compiling OTR Logic only.")
endif()

add_library(bkawrapper SHARED ${ALL_SOURCES})

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
    -w -fcommon -O2
)

find_library(log-lib log)
find_library(opensl-lib OpenSLES)
target_link_libraries(bkawrapper android ${log-lib} ${opensl-lib} GLESv3 EGL)
