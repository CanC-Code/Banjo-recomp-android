cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Define the Option (This allows the -DEXCLUDE_GAME_SRC flag to work)
option(EXCLUDE_GAME_SRC "Exclude game source files for faster verification" ON)

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# 2. Base Bridge Sources (Always compiled)
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

# 3. Conditionally Add the Full Game Source
if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "BKA: EXCLUDE_GAME_SRC is OFF. Collecting game source files...")
    
    # This finds every .c and .cpp file in your /src directory recursively
    file(GLOB_RECURSE GAME_SOURCES 
        "${REPO_ROOT}/src/*.c"
        "${REPO_ROOT}/src/*.cpp"
    )
    
    # Add them to our list of files to compile
    list(APPEND LIB_SOURCES ${GAME_SOURCES})
else()
    message(STATUS "BKA: EXCLUDE_GAME_SRC is ON. Compiling bridge only.")
endif()

# Create the library using our full list of sources
add_library(bkawrapper SHARED ${LIB_SOURCES})

# 4. Include Paths
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src            # <--- Added so game files can find their internal headers
    ${REPO_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# 5. Compilation Options
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"        # Suppresses the massive wall of warnings from the original C code
    "-O3"       # Maximum optimization for the game engine
)

# 6. Linking
find_library(log-lib log)
target_link_libraries(bkawrapper 
    android 
    ${log-lib} 
    GLESv3 
    EGL
    z
)
