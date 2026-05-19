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

    private static final String TAG              = "BKA-MainActivity";
    private static final int    PICK_ROM_REQUEST = 1001;

    private static final String SENTINEL_FILENAME = "extraction_complete";

    private View        menuOverlay;
    private View        otrContainer;
    private ProgressBar progressBar;
    private TextView    progressText;
    private TextView    currentArtifactText;

    private GLSurfaceView glSurfaceView;

    static {
        System.loadLibrary("bkawrapper");
    }

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

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (hasExtractionCompleted()) {
            Log.i(TAG, "Extraction sentinel and base ROM verified — skipping ROM selection");
            bootGameEngine();
        } else {
            setContentView(R.layout.activity_main);
            neutralizeXmlGLSurfaceView((ViewGroup) findViewById(android.R.id.content));

            menuOverlay         = findViewById(R.id.menu_overlay);
            otrContainer        = findViewById(R.id.otr_ui_container);
            progressBar         = findViewById(R.id.otr_progress_bar);
            progressText        = findViewById(R.id.otr_progress_text);
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
        LocalBroadcastManager.getInstance(this).registerReceiver(progressReceiver, filter);

        if (glSurfaceView != null) glSurfaceView.onResume();
    }

    @Override
    protected void onPause() {
        super.onPause();
        LocalBroadcastManager.getInstance(this).unregisterReceiver(progressReceiver);
        if (glSurfaceView != null) glSurfaceView.onPause();
    }

    // CRITICAL CORRECTION: Do not trust the sentinel file alone. Verify the C++ 
    // engine actually dropped the required physical payload.
    private boolean hasExtractionCompleted() {
        File sentinel = new File(getFilesDir(), SENTINEL_FILENAME);
        File romBase  = new File(getFilesDir(), "rom_base.bin");
        
        if (sentinel.exists() && (!romBase.exists() || romBase.length() < 4096)) {
            Log.w(TAG, "False sentinel detected (Silent Abort). Wiping corrupt state.");
            sentinel.delete();
            romBase.delete();
            return false;
        }
        return sentinel.exists() && romBase.exists();
    }

    private void neutralizeXmlGLSurfaceView(ViewGroup group) {
        if (group == null) return;
        for (int i = 0; i < group.getChildCount(); i++) {
            View child = group.getChildAt(i);
            if (child instanceof GLSurfaceView) {
                GLSurfaceView dummy = (GLSurfaceView) child;
                dummy.setEGLContextClientVersion(3);
                dummy.setRenderer(new GLSurfaceView.Renderer() {
                    @Override public void onSurfaceCreated(GL10 gl, EGLConfig config) {}
                    @Override public void onSurfaceChanged(GL10 gl, int width, int height) {}
                    @Override public void onDrawFrame(GL10 gl) {}
                });
                dummy.setRenderMode(GLSurfaceView.RENDERMODE_WHEN_DIRTY);
            } else if (child instanceof ViewGroup) {
                neutralizeXmlGLSurfaceView((ViewGroup) child);
            }
        }
    }

    public void openFilePicker() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, PICK_ROM_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_ROM_REQUEST && resultCode == RESULT_OK && data != null) {
            Uri romUri = data.getData();
            if (romUri != null) {
                final int takeFlags = data.getFlags() & (Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                try {
                    getContentResolver().takePersistableUriPermission(romUri, takeFlags);
                } catch (SecurityException e) {
                    Log.w(TAG, "Could not take persistable permissions, proceeding with temporary", e);
                }
                startExtraction(romUri);
            }
        }
    }

    private void startExtraction(Uri romUri) {
        if (menuOverlay != null) menuOverlay.setVisibility(View.GONE);
        if (otrContainer != null) otrContainer.setVisibility(View.VISIBLE);

        Intent serviceIntent = new Intent(this, OtrService.class);
        serviceIntent.putExtra("uri",    romUri.toString());
        serviceIntent.putExtra("outDir", getFilesDir().getAbsolutePath());
        startService(serviceIntent);
    }

    private void updateUI(int percent, String fileName) {
        if (progressBar         != null) progressBar.setProgress(percent);
        if (progressText        != null) progressText.setText(percent + "%");
        if (currentArtifactText != null) currentArtifactText.setText(fileName);
    }

    private void handleExtractionComplete() {
        if (currentArtifactText != null) currentArtifactText.setText("Booting Banjo-Kazooie...");
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
        Toast.makeText(this, "Extraction failed: " + message, Toast.LENGTH_LONG).show();
    }

    private void bootGameEngine() {
        final String assetDir    = getFilesDir().getAbsolutePath();
        final AssetManager mgr   = getAssets();

        glSurfaceView = new GLSurfaceView(this);
        glSurfaceView.setEGLContextClientVersion(3);
        glSurfaceView.setEGLConfigChooser(8, 8, 8, 8, 24, 8);
        glSurfaceView.setPreserveEGLContextOnPause(true);

        glSurfaceView.setRenderer(new GLRenderer(this, assetDir, mgr));
        glSurfaceView.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);

        setContentView(glSurfaceView);
    }
}
