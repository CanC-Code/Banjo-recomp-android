#ifndef OTR_BUILDER_H
#define OTR_BUILDER_H

#include <jni.h>
#include <stdint.h>

extern "C" {
    void otr_builder_set_jvm(JavaVM* vm);
    void run_native_otr_generation_with_callback(JNIEnv* env, jobject activity, jmethodID progressMid,
                                               int romFd, uint8_t* manifestPtr, uint32_t manifestSize, 
                                               const char* outDirPath);
}

#endif
