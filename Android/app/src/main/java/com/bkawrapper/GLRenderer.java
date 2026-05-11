// File: Android/app/src/main/java/com/bkawrapper/GLRenderer.java
package com.bkawrapper;

import android.content.Context;
import android.content.res.AssetManager;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.util.Log;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/**
 * GLRenderer
 *
 * Drives the N64 framebuffer → Android display pipeline.
 */
public class GLRenderer implements GLSurfaceView.Renderer {

    private static final String TAG = "BKA-GLRenderer";

    private final Context context;
    private final String assetDir;
    private final AssetManager mgr;

    // CRITICAL FIX: Make this static. C++ game engines typically cannot survive 
    // a second boot in the same process memory space. This prevents double-booting 
    // when Android recreates the Activity (e.g., on screen rotation).
    private static boolean engineBooted = false;
    
    // Gatekeeper to prevent native rendering before the viewport is established
    private boolean isSurfaceReady = false;

    public GLRenderer(Context context, String assetDir, AssetManager mgr) {
        this.context = context;
        this.assetDir = assetDir;
        this.mgr = mgr;
    }

    // -----------------------------------------------------------------------
    // GLSurfaceView.Renderer callbacks — all called on the GL thread
    // -----------------------------------------------------------------------

    @Override
    public void onSurfaceCreated(GL10 gl, EGLConfig config) {
        Log.i(TAG, "onSurfaceCreated: GL context ready");

        // Set a black clear colour so we don't get garbage on first frame
        GLES20.glClearColor(0f, 0f, 0f, 1f);
        
        // Note: NativeBridge.surfaceReady is deferred to onSurfaceChanged 
        // to ensure the C++ engine receives the true device resolution.
    }

    @Override
    public void onSurfaceChanged(GL10 gl, int width, int height) {
        Log.i(TAG, "onSurfaceChanged: " + width + "×" + height);
        GLES20.glViewport(0, 0, width, height);

        // Tell the native side the GL context is alive and provide ACTUAL dimensions
        NativeBridge.surfaceReady(width, height);
        isSurfaceReady = true;

        // Run the blocking game loop on a dedicated background thread.
        // Protected by the static flag so it only runs once per app process.
        if (!engineBooted) {
            engineBooted = true;
            new Thread(() -> {
                Log.i(TAG, "Game thread starting — assetDir=" + assetDir);
                NativeBridge.nativeGameBoot(assetDir, mgr);
                Log.w(TAG, "nativeGameBoot returned — game has exited");
            }, "BKA-GameThread").start();
        }
    }

    @Override
    public void onDrawFrame(GL10 gl) {
        // Guard against calling updateTexture before the native side knows about the surface
        if (isSurfaceReady) {
            // Clear the screen buffer before asking native to draw the quad
            GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);
            NativeBridge.updateTexture(0);
        }
    }
}
