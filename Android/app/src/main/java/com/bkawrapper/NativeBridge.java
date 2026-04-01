package com.bkawrapper;

import android.content.res.AssetManager;

public class NativeBridge {

    // Load the native C++ library compiled by CMake
    static {
        System.loadLibrary("ultra"); 
    }

    /**
     * Bootstraps the N64 environment and starts the game loop.
     * * @param otrPath      The absolute path to the extracted assets directory.
     * @param assetManager Android's AssetManager to read the manifest.
     */
    public static native void nativeGameBoot(String otrPath, AssetManager assetManager);

    /**
     * Updates the N64 controller state.
     * * @param buttonMask Bitmask of currently pressed buttons.
     * @param stickX     Analog stick X-axis (-80 to 80).
     * @param stickY     Analog stick Y-axis (-80 to 80).
     */
    public static native void nativeUpdateInput(int buttonMask, float stickX, float stickY);
}
