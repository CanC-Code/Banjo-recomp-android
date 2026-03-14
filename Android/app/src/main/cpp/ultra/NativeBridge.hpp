#ifndef NATIVE_BRIDGE_HPP
#define NATIVE_BRIDGE_HPP

#include <jni.h>

class NativeBridge {
public:
    static void initialize(JavaVM* vm);
private:
    static JavaVM* s_vm;
};

#endif
