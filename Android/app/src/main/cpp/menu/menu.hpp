#pragma once
#include <jni.h>

class MenuHandler {
public:
    MenuHandler(JavaVM* vm, jobject activity);
    ~MenuHandler();

    void toggleVisibility();
    bool isVisible() const;

private:
    JavaVM* vm_;
    jobject menuOverlayGlobal_;
    bool visible_ = false;

    void setVisibility(bool visible);
};