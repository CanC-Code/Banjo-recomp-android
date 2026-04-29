// File: Android/app/src/main/java/com/bkawrapper/NativeBridge.java
package com.bkawrapper;

import android.content.res.AssetManager;

public class NativeBridge {

    // Load the native C++ library compiled by CMake.
    // This MUST match the name in CMakeLists.txt: add_library(bkawrapper ...)
    static {
        System.loadLibrary("bkawrapper");
    }

    /**
     * Initializes the JNI bridge so C++ can call back into Java for progress
     * updates.
     *
     * @param service The OtrService instance (usually 'this').
     */
    public static native void nativeInit(OtrService service);

    /**
     * Extracts ROM assets into {@code outDir} as loose files.
     * Calls {@code service.updateOtrProgress()} periodically via JNI.
     *
     * @param fd           File descriptor for the ROM (detached from a
     *                     ParcelFileDescriptor — C++ owns it after this call).
     * @param assetManager Used to read manifest_us.bin from the APK.
     * @param outDir       Destination directory (getFilesDir()).
     */
    public static native void runOtrGeneration(int fd,
                                               AssetManager assetManager,
                                               String outDir);

    /**
     * Initialises the engine and enters the main game loop (blocking).
     * Must be called on a dedicated background thread.
     *
     * @param otrPath      Path to the directory containing extracted assets
     *                     (same value passed as {@code outDir} to
     *                     {@link #runOtrGeneration}).
     * @param assetManager Used to re-open manifest_us.bin for ResourceMgr.
     */
    public static native void nativeGameBoot(String otrPath,
                                             AssetManager assetManager);

    /**
     * Notifies the native layer that the GL surface is created and a texture
     * can be allocated.  Must be called from the GL thread inside
     * {@code onSurfaceCreated}.
     *
     * @param width  Surface pixel width.
     * @param height Surface pixel height.
     */
    public static native void surfaceReady(int width, int height);

    /**
     * Uploads the current N64 framebuffer to the GL texture and draws a
     * fullscreen quad.  Called every frame from the GL thread.
     *
     * @param unused Reserved / ignored.
     */
    public static native void updateTexture(int unused);

    /**
     * Pushes controller state into the N64 input emulation layer.
     *
     * @param buttonMask N64 button bitmask (see PR/os_cont.h).
     * @param stickX     Analogue stick X in [-1, 1].
     * @param stickY     Analogue stick Y in [-1, 1].
     */
    public static native void nativeUpdateInput(int   buttonMask,
                                                float stickX,
                                                float stickY);
}
