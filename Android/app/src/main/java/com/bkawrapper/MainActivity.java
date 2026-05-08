// File: Android/app/src/main/java/com/bkawrapper/MainActivity.java
package com.bkawrapper;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.res.AssetManager;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import android.opengl.GLSurfaceView;

import java.io.File;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

public class MainActivity extends AppCompatActivity {

    private static final String TAG             = "BKA-MainActivity";
    private static final int    PICK_ROM_REQUEST = 1001;

    // Name of a sentinel file we write when extraction finishes successfully.
    // Checking for this one file is faster and more reliable than scanning
    // for individual asset files (the asset directory can have hundreds of
    // entries with no fixed extension).
    private static final String SENTINEL_FILENAME = "extraction_complete";

    private View        menuOverlay;
    private View        otrContainer;
    private ProgressBar progressBar;
    private TextView    progressText;
    private TextView    currentArtifactText;

    // Kept so we can pause/resume the GL surface correctly
    private GLSurfaceView glSurfaceView;

    // -----------------------------------------------------------------------
    // Broadcast receiver – listens for progress/completion from OtrService
    // -----------------------------------------------------------------------
    private final BroadcastReceiver progressReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (action == null) return;

            switch (action) {
                case OtrService.ACTION_OTR_PROGRESS: {
                    int    percent = intent.getIntExtra("percent", 0);
                    String status  = intent.getStringExtra("status");
                    updateUI(percent, status);
                    break;
                }
                case OtrService.ACTION_OTR_COMPLETE:
                    handleExtractionComplete();
                    break;

                case OtrService.ACTION_OTR_ERROR: {
                    String error = intent.getStringExtra("message");
                    handleExtractionError(error);
                    break;
                }
            }
        }
    };

    // -----------------------------------------------------------------------
    // Activity lifecycle
    // -----------------------------------------------------------------------

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (hasExtractionCompleted()) {
            // Assets are already on disk — go straight to the game
            Log.i(TAG, "Extraction sentinel found — skipping ROM selection");
            bootGameEngine();
        } else {
            // First run: show ROM selection menu
            setContentView(R.layout.activity_main);

            // Neutralize any uninitialized GLSurfaceView in the XML to prevent surfaceCreated crashes
            neutralizeXmlGLSurfaceView((ViewGroup) findViewById(android.R.id.content));

            menuOverlay        = findViewById(R.id.menu_overlay);
            otrContainer       = findViewById(R.id.otr_ui_container);
            progressBar        = findViewById(R.id.otr_progress_bar);
            progressText       = findViewById(R.id.otr_progress_text);
            currentArtifactText = findViewById(R.id.otr_current_artifact);

            new MenuController(this);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        IntentFilter filter = new IntentFilter();
        filter.addAction(OtrService.ACTION_OTR_PROGRESS);
        filter.addAction(OtrService.ACTION_OTR_COMPLETE);
        filter.addAction(OtrService.ACTION_OTR_ERROR);
        LocalBroadcastManager.getInstance(this)
                             .registerReceiver(progressReceiver, filter);

        if (glSurfaceView != null) {
            glSurfaceView.onResume();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        LocalBroadcastManager.getInstance(this)
                             .unregisterReceiver(progressReceiver);
        if (glSurfaceView != null) {
            glSurfaceView.onPause();
        }
    }

    // -----------------------------------------------------------------------
    // Extraction-complete sentinel
    // -----------------------------------------------------------------------

    /**
     * Returns true if the sentinel file created at the end of a successful
     * extraction exists in getFilesDir().
     */
    private boolean hasExtractionCompleted() {
        File sentinel = new File(getFilesDir(), SENTINEL_FILENAME);
        return sentinel.exists();
    }

    /**
     * Creates the sentinel file.  Called by OtrService (via broadcast) after
     * a successful extraction so subsequent launches skip re-extraction.
     */
    public void writeExtractionSentinel() {
        try {
            File sentinel = new File(getFilesDir(), SENTINEL_FILENAME);
            if (!sentinel.exists()) {
                //noinspection ResultOfMethodCallIgnored
                sentinel.createNewFile();
                Log.i(TAG, "Sentinel written: " + sentinel.getAbsolutePath());
            }
        } catch (Exception e) {
            Log.w(TAG, "Could not write sentinel: " + e.getMessage());
        }
    }

    // -----------------------------------------------------------------------
    // UI safeguards
    // -----------------------------------------------------------------------

    /**
     * Scans the inflated XML layout for any placeholder GLSurfaceViews and assigns
     * a non-functional dummy renderer. This prevents the WindowManager from crashing 
     * on a null GLThread while the app waits for the background extraction to finish.
     */
    private void neutralizeXmlGLSurfaceView(ViewGroup group) {
        if (group == null) return;
        for (int i = 0; i < group.getChildCount(); i++) {
            View child = group.getChildAt(i);
            if (child instanceof GLSurfaceView) {
                GLSurfaceView dummy = (GLSurfaceView) child;
                dummy.setEGLContextClientVersion(2);
                dummy.setRenderer(new GLSurfaceView.Renderer() {
                    @Override
                    public void onSurfaceCreated(GL10 gl, EGLConfig config) {}
                    @Override
                    public void onSurfaceChanged(GL10 gl, int width, int height) {}
                    @Override
                    public void onDrawFrame(GL10 gl) {}
                });
                // Only render when explicitly told to, saving battery during extraction
                dummy.setRenderMode(GLSurfaceView.RENDERMODE_WHEN_DIRTY);
            } else if (child instanceof ViewGroup) {
                neutralizeXmlGLSurfaceView((ViewGroup) child);
            }
        }
    }

    // -----------------------------------------------------------------------
    // ROM picker
    // -----------------------------------------------------------------------

    public void openFilePicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, PICK_ROM_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_ROM_REQUEST
                && resultCode == RESULT_OK
                && data != null) {
            startExtraction(data.getData());
        }
    }

    private void startExtraction(Uri romUri) {
        menuOverlay.setVisibility(View.GONE);
        otrContainer.setVisibility(View.VISIBLE);

        Intent serviceIntent = new Intent(this, OtrService.class);
        serviceIntent.putExtra("uri",    romUri.toString());
        serviceIntent.putExtra("outDir", getFilesDir().getAbsolutePath());
        startService(serviceIntent);
    }

    // -----------------------------------------------------------------------
    // UI helpers (run on main thread via broadcast receiver)
    // -----------------------------------------------------------------------

    private void updateUI(int percent, String fileName) {
        if (progressBar        != null) progressBar.setProgress(percent);
        if (progressText       != null) progressText.setText(percent + "%");
        if (currentArtifactText != null) currentArtifactText.setText(fileName);
    }

    private void handleExtractionComplete() {
        // Write the sentinel so next launch goes straight to the game
        writeExtractionSentinel();

        if (currentArtifactText != null) {
            currentArtifactText.setText("Booting Banjo-Kazooie...");
        }

        if (otrContainer != null) {
            otrContainer.postDelayed(() -> {
                otrContainer.setVisibility(View.GONE);
                bootGameEngine();
            }, 800);
        } else {
            bootGameEngine();
        }
    }

    private void handleExtractionError(String message) {
        if (otrContainer  != null) otrContainer.setVisibility(View.GONE);
        if (menuOverlay   != null) menuOverlay.setVisibility(View.VISIBLE);
        Toast.makeText(this,
                       "Extraction failed: " + message,
                       Toast.LENGTH_LONG).show();
    }

    // -----------------------------------------------------------------------
    // Game boot
    // -----------------------------------------------------------------------

    private void bootGameEngine() {
        final String assetDir    = getFilesDir().getAbsolutePath();
        final AssetManager mgr   = getAssets();

        // Build and attach the GL surface (this dynamically replaces the dummy XML view)
        glSurfaceView = new GLSurfaceView(this);
        glSurfaceView.setEGLContextClientVersion(2);   // GLES 2.0 context
        glSurfaceView.setRenderer(new GLRenderer(this, assetDir, mgr));
        // RENDERMODE_CONTINUOUSLY: the renderer's onDrawFrame is called as
        // fast as the display will allow (vsync-paced by the driver).
        glSurfaceView.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);

        setContentView(glSurfaceView);
    }
}
