#include <jni.h>
#include <android/log.h>

// Helper to ensure C++ can talk back to Java safely
void ShowMenuNative(JavaVM* vm, jobject activityInstance) {
    JNIEnv* env = nullptr;
    if (vm->GetEnv((void**)&env, JNI_VERSION_1_6) != JNI_OK) {
        vm->AttachCurrentThread(&env, nullptr);
    }

    if (env != nullptr) {
        __android_log_print(ANDROID_LOG_INFO, "Menu", "Menu requested by Java Activity");
        // Logic to trigger UI would go here
    }
}
