cmake_minimum_required(VERSION 3.22.1)
project("bkawrapper")

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)

# --- 1. Define Native Port Infrastructure ---
set(VERIFICATION_SOURCES
    "ultra/NativeBridge.cpp"
    "ultra/otr_builder.cpp"
    "ultra/parameters.cpp"
    "ultra/libm_vals.cpp"
    "emulator/stubs.cpp"
    "emulator/pi_hle.cpp"
    "emulator/resource_mgr.cpp"
    "tools/rare_decompression.cpp" 
)

# --- 2. Original N64 Source Integration ---
option(EXCLUDE_GAME_SRC "Skip the main game source files" OFF)

if(NOT EXCLUDE_GAME_SRC)
    message(STATUS "Including original N64 source files from ${REPO_ROOT}/src")

    # Recursively find all C files
    file(GLOB_RECURSE GAME_SOURCES "${REPO_ROOT}/src/*.c")

    # --- THE CRITICAL FIX: VERSION & SYMBOL PRUNING ---
    
    # 1. Improved Version Filtering
    # This logic identifies and removes files with region tags (like .us.v10.c)
    # to prevent duplicates with the base files (like code_46C0.c).
    set(VERSIONED_FILES "")
    foreach(FILE_PATH ${GAME_SOURCES})
        if(${FILE_PATH} MATCHES ".*\\.(us|pal|jp|v10|v11).*\\.c$")
            list(APPEND VERSIONED_FILES ${FILE_PATH})
        endif()
    endforeach()

    # 2. Identify System & Subsystem Conflicts
    # Note: We do NOT exclude src/done/ here anymore, as it provides osStartThread.
    file(GLOB_RECURSE SYSTEM_CONFLICTS 
        "${REPO_ROOT}/src/core1/os/*.c"      # Original O/S logic (use /src/done/ instead)
        "${REPO_ROOT}/src/core1/io/*.c"      # Original I/O logic (use /src/done/ instead)
        "${REPO_ROOT}/src/core1/audio/sl.c"  # Conflicts with stubs.cpp (alGlobals)
        "${REPO_ROOT}/src/core1/code_0.c"    # Conflicts with stubs.cpp (mainLoop)
        "${REPO_ROOT}/src/core1/code_7F60.c" # Duplicated library function
    )
    
    # Apply the pruning
    if(VERSIONED_FILES)
        list(REMOVE_ITEM GAME_SOURCES ${VERSIONED_FILES})
        message(STATUS "Pruned region-specific duplicates (e.g. .us.v10.c).")
    endif()
    
    if(SYSTEM_CONFLICTS)
        list(REMOVE_ITEM GAME_SOURCES ${SYSTEM_CONFLICTS})
        message(STATUS "Pruned OS/Audio library conflicts.")
    endif()

    set(ALL_SOURCES ${VERIFICATION_SOURCES} ${GAME_SOURCES})
else()
    set(ALL_SOURCES ${VERIFICATION_SOURCES})
endif()

add_library(bkawrapper SHARED ${ALL_SOURCES})

# --- 3. Include Paths ---
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

# --- 4. Compilation Flags ---
target_compile_options(bkawrapper PRIVATE 
    "-include" "${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    "-w"                           
    "-fpermissive"                 
    "-Wno-error=implicit-int"      
    "-Wno-error=int-conversion"    
    "-Wno-error=implicit-function-declaration"
    "-Wno-error=incompatible-pointer-types"
)

target_compile_definitions(bkawrapper PRIVATE F3DEX_GBI)

# --- 5. Linking ---
find_library(log-lib log)
target_link_libraries(bkawrapper android ${log-lib} GLESv3 EGL z)
