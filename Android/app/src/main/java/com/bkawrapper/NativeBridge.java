package com.bkawrapper;

import android.content.res.AssetManager;

public class NativeBridge {

    // Load the native C++ library compiled by CMake.
    // This MUST match the name in CMakeLists.txt: add_library(bkawrapper ...)
    static {
        System.loadLibrary("bkawrapper"); 
    }

    /**
     * Initializes the bridge so C++ can send progress updates back to Java.
     * @param service The OtrService instance (usually 'this').
     */
    public static native void nativeInit(OtrService service);

    /**
     * Generates OTR asset files from the provided ROM file descriptor.
     * @param fd           The file descriptor for the ROM file.
     * @param assetManager Used to read the manifest from the APK.
     * @param outDir       Where to save the extracted assets.
     */
    public static native void runOtrGeneration(int fd, AssetManager assetManager, String outDir);

    /**
     * Bootstraps the N64 environment and starts the game loop.
     * @param otrPath      The path where assets were extracted.
     * @param assetManager Used to read bridge-specific assets.
     */
    public static native void nativeGameBoot(String otrPath, AssetManager assetManager);

    /**
     * Updates the N64 controller state.
     */
    public static native void nativeUpdateInput(int buttonMask, float stickX, float stickY);

    /**
     * Optional: Update logic for textures. 
     * If not implemented in C++, this can remain a stub.
     */
    public static native void updateTexture(int textureStub);
}
