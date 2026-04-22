cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# Define Paths
set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(GAME_INC ${REPO_ROOT}/include)

# 1. Essential OTR Logic (Keep these)
set(OTR_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "emulator/stubs.cpp"
)

# 2. Toggle Logic
option(EXCLUDE_GAME_SRC "Exclude N64 source for verification" OFF)

if(EXCLUDE_GAME_SRC)
    message(STATUS "Verification Build: Skipping N64 system files")
    add_definitions(-DNO_GAME_SRC)
    set(ALL_SOURCES ${OTR_SOURCES})
else()
    # Full Build: Include everything
    file(GLOB_RECURSE EMULATOR_SRC "emulator/*.cpp")
    file(GLOB_RECURSE ULTRA_SRC "ultra/*.cpp")
    set(ALL_SOURCES ${EMULATOR_SRC} ${ULTRA_SRC})
endif()

add_library(bkawrapper SHARED ${ALL_SOURCES})

# Include Paths
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${GAME_INC}
    ${GAME_INC}/2.0L
    ${GAME_INC}/2.0L/PR
)

# Force-include our types header in every file
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
)

# Link Libraries
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL)
