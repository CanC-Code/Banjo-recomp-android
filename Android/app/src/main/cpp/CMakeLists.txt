cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

# 1. Define the option
option(EXCLUDE_GAME_SRC "Exclude game source" ON)

# 2. Establish the Repo Root
# Current: Android/app/src/main/cpp -> ../../../../../ -> Root
set(REPO_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../../..")
get_filename_component(REAL_ROOT "${REPO_ROOT}" ABSOLUTE)

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

# 3. The Logic
if(EXCLUDE_GAME_SRC)
    message(STATUS "BKA-BUILD: Bridge only mode enabled.")
else()
    message(STATUS "BKA-BUILD: Attempting full game build...")
    message(STATUS "BKA-BUILD: Looking for source in: ${REAL_ROOT}/src")

    file(GLOB_RECURSE GAME_C "${REAL_ROOT}/src/*.c")
    file(GLOB_RECURSE GAME_CPP "${REAL_ROOT}/src/*.cpp")
    
    set(GAME_FILES ${GAME_C} ${GAME_CPP})
    list(LENGTH GAME_FILES FILE_COUNT)

    # --- FAIL-SAFE CHECK ---
    if(FILE_COUNT EQUAL 0)
        message(FATAL_ERROR "
        CRITICAL ERROR: No game source files found! 
        Looked in: ${REAL_ROOT}/src
        Make sure the /src folder exists in your repository root.
        ")
    endif()

    message(STATUS "BKA-BUILD: Found ${FILE_COUNT} files. Compiling...")
    list(APPEND LIB_SOURCES ${GAME_FILES})
endif()

add_library(bkawrapper SHARED ${LIB_SOURCES})

# 4. Includes
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REAL_ROOT}/include
    ${REAL_ROOT}/include/2.0L
    ${REAL_ROOT}/src
    ${REAL_ROOT}/tools/bk_rom_compressor/modules/rarezip
)

# 5. Options & Linking
target_compile_options(bkawrapper PRIVATE "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h" "-w" "-O3")
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
