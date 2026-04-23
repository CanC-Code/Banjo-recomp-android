cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Force CMake to recognize the command-line flag
# Default is ON so it stays fast unless we explicitly flip it in GitHub
option(EXCLUDE_GAME_SRC "Exclude game source" ON)

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# 2. Base bridge sources
set(LIB_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"
    "emulator/pi_hle.cpp"
    "emulator/resource_mgr.cpp"
    "tools/rare_decompression.cpp" 
)

# 3. The Game Source Logic
if(EXCLUDE_GAME_SRC)
    message(STATUS "!!! BKA: BUILDING BRIDGE ONLY (FAST MODE) !!!")
else()
    message(STATUS "!!! BKA: BUILDING FULL GAME ENGINE (SLOW MODE) !!!")
    
    # Recursively find all C files in the repo root /src
    file(GLOB_RECURSE GAME_C_FILES "${REPO_ROOT}/src/*.c")
    file(GLOB_RECURSE GAME_CPP_FILES "${REPO_ROOT}/src/*.cpp")
    
    list(APPEND LIB_SOURCES ${GAME_C_FILES} ${GAME_CPP_FILES})
    
    # Debug: Print how many files we found
    list(LENGTH LIB_SOURCES TOTAL_FILE_COUNT)
    message(STATUS "BKA: Total files added to build: ${TOTAL_FILE_COUNT}")
endif()

add_library(bkawrapper SHARED ${LIB_SOURCES})

# 4. Include Paths
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

# 5. Options
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"
    "-O3" 
)

# 6. Linking
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
