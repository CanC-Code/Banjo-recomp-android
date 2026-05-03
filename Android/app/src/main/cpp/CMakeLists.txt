cmake_minimum_required(VERSION 3.22.1)
project(bkawrapper)

set(REPO_ROOT ${CMAKE_CURRENT_SOURCE_DIR}/../../../../..)
set(TARGET_VERSION "us.v10")

# ============================================================
# 1. Bridge Sources
# ============================================================
set(BRIDGE_SOURCES
    ultra/NativeBridge.cpp
    ultra/otr_builder.cpp
    ultra/parameters.cpp
    ultra/libm_vals.cpp          
    ultra/exceptasm.cpp          
    ultra/LinkerSymbols.cpp      
    ultra/setintmask.cpp         
    ultra/math_bridge.cpp
    ultra/audio_bridge.cpp
    ultra/lowlevel_bridge.cpp
    emulator/stubs.cpp
    emulator/pi_hle.cpp
    emulator/resource_mgr.cpp
    tools/rare_decompression.cpp
    ultra/HardwareRegs.cpp

    # Dead-stub fallbacks — must be last
    ultra/missing_stubs.c
)

# ============================================================
# 2. Game Source Files (Including .cpp for Engine Core)
# ============================================================
option(EXCLUDE_GAME_SRC "Skip compiling the recompiled game source tree" OFF)

set(GAME_SOURCES "")
if(NOT EXCLUDE_GAME_SRC)
    # UPDATED: Glob both .c and .cpp to ensure main_loop and engine core are captured
    file(GLOB_RECURSE ALL_GAME_FILES 
        "${REPO_ROOT}/src/*.c"
        "${REPO_ROOT}/src/*.cpp"
    )

    # The Hardware & OS Blacklist
    set(EXCLUSION_LIST
        "pirawdma.c"   
        "epirawdma.c"  
        "pimgr.c"      
        "vi.c"         
        "vicurrent.c"  
        "osYield.c"    
        "recvmesg.c"   
        "sendmesg.c"   
        "jammesg.c"    
    )

    foreach(FILE_PATH ${ALL_GAME_FILES})
        get_filename_component(FILENAME ${FILE_PATH} NAME)
        list(FIND EXCLUSION_LIST ${FILENAME} INDEX)
        if(INDEX EQUAL -1)
            list(APPEND GAME_SOURCES ${FILE_PATH})
        else()
            message(STATUS "BKA-BUILD: Excluding N64 OS/HW file: ${FILE_PATH}")
        endif()
    endforeach()
endif()

# ============================================================
# 3. Add Library
# ============================================================
add_library(bkawrapper SHARED
    ${BRIDGE_SOURCES}
    ${GAME_SOURCES}
)

# ============================================================
# 4. Include Directories
# ============================================================
target_include_directories(bkawrapper PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/ultra
    ${CMAKE_CURRENT_SOURCE_DIR}/emulator
    ${CMAKE_CURRENT_SOURCE_DIR}/tools
    ${REPO_ROOT}/include
    ${REPO_ROOT}/include/2.0L
    ${REPO_ROOT}/src
)

# ============================================================
# 5. Compile Options
# ============================================================
target_compile_options(bkawrapper PRIVATE
    "-include${CMAKE_CURRENT_SOURCE_DIR}/ultra/n64_types.h"
    -w
    -fpermissive
    -Wno-error=implicit-int
    -Wno-error=int-conversion
    -Wno-error=implicit-function-declaration
    -Wno-error=incompatible-pointer-types
    -Wno-error=unused-function

    $<$<COMPILE_LANGUAGE:CXX>:-std=c++17>
    $<$<COMPILE_LANGUAGE:C>:-std=gnu11>
)

# ============================================================
# 6. Defines & Linking
# ============================================================
target_compile_definitions(bkawrapper PRIVATE
    F3DEX_GBI
    N64_RECOMP
    VERSION=0
    __ANDROID__
)

find_library(log-lib     log)
find_library(android-lib android)
find_library(gles3-lib   GLESv3)
find_library(gles2-lib   GLESv2)
find_library(z-lib       z)

target_link_libraries(bkawrapper
    ${log-lib}
    ${android-lib}
    ${gles3-lib}
    ${gles2-lib}
    ${z-lib}
    atomic
    m
)

# Force the linker to ignore multiple definitions (common in recompiled ports)
# and ensure symbols like main_loop are visible.
target_link_options(bkawrapper PRIVATE 
    "-Wl,--allow-multiple-definition"
    "-Wl,--export-dynamic"
)
