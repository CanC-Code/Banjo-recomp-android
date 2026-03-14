#include <jni.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "n64_types.h"

// We no longer need to include libaudio.h here because n64_types.h handles the core types
// and we only need the alGlobals pointer which is handled by the linker.

extern "C" {
    void mainLoop(void);
    void ResourceMgr_Init(const char* otrPath, uint8_t* manifestBuf, uint32_t manifestSize);
    
    // The linker will find this in the compiled core1/audio files
    extern void* alGlobals; 
}

extern "C" {
JNIEXPORT void JNICALL
Java_com_bkawrapper_NativeBridge_nativeGameBoot(JNIEnv* env, jclass clazz, jstring otrPath, jobject assetManager) {
    if (alGlobals == nullptr) {
        alGlobals = malloc(8192); 
        memset(alGlobals, 0, 8192);
    }
    // Boot logic...
    mainLoop();
}
}
