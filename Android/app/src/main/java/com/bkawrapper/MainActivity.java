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
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import androidx.appcompat.app.AppCompatActivity;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

public class MainActivity extends AppCompatActivity {
    private static final String TAG = "BKA-MainActivity";
    private static final int PICK_ROM_REQUEST = 1001;

    private View menuOverlay;
    private View otrContainer;
    private ProgressBar progressBar;
    private TextView progressText;
    private TextView currentArtifactText;

    private final BroadcastReceiver progressReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();

            if (OtrService.ACTION_OTR_PROGRESS.equals(action)) {
                int percent = intent.getIntExtra("percent", 0);
                String status = intent.getStringExtra("status");
                updateUI(percent, status);

            } else if (OtrService.ACTION_OTR_COMPLETE.equals(action)) {
                // The "Final Boss" has been defeated. Boot the game!
                handleExtractionComplete();

            } else if (OtrService.ACTION_OTR_ERROR.equals(action)) {
                String error = intent.getStringExtra("message");
                handleExtractionError(error);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        menuOverlay = findViewById(R.id.menu_overlay);
        otrContainer = findViewById(R.id.otr_ui_container);
        progressBar = findViewById(R.id.otr_progress_bar);
        progressText = findViewById(R.id.otr_progress_text);
        currentArtifactText = findViewById(R.id.otr_current_artifact);

        new MenuController(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        IntentFilter filter = new IntentFilter();
        filter.addAction(OtrService.ACTION_OTR_PROGRESS);
        filter.addAction(OtrService.ACTION_OTR_COMPLETE);
        filter.addAction(OtrService.ACTION_OTR_ERROR);
        LocalBroadcastManager.getInstance(this).registerReceiver(progressReceiver, filter);
    }

    @Override
    protected void onPause() {
        super.onPause();
        LocalBroadcastManager.getInstance(this).unregisterReceiver(progressReceiver);
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
            startExtraction(data.getData());
        }
    }

    private void startExtraction(Uri romUri) {
        menuOverlay.setVisibility(View.GONE);
        otrContainer.setVisibility(View.VISIBLE);

        Intent serviceIntent = new Intent(this, OtrService.class);
        serviceIntent.putExtra("uri", romUri.toString());
        serviceIntent.putExtra("outDir", getFilesDir().getAbsolutePath());
        startService(serviceIntent);
    }

    private void updateUI(int percent, String fileName) {
        progressBar.setProgress(percent);
        progressText.setText(percent + "%");
        currentArtifactText.setText(fileName);
    }

    private void handleExtractionComplete() {
        currentArtifactText.setText("Booting Banjo-Kazooie Engine...");
        
        // Brief delay to let the user see the 100% state before the game starts
        otrContainer.postDelayed(() -> {
            otrContainer.setVisibility(View.GONE);
            bootGameEngine();
        }, 1000);
    }

    private void handleExtractionError(String message) {
        otrContainer.setVisibility(View.GONE);
        menuOverlay.setVisibility(View.VISIBLE);
        Toast.makeText(this, "Extraction Failed: " + message, Toast.LENGTH_LONG).show();
    }

    private void bootGameEngine() {
        new Thread(() -> {
            Log.i(TAG, "Entering nativeGameBoot...");
            String otrPath = getFilesDir().getAbsolutePath();
            AssetManager assetManager = getAssets();
            
            // This starts the infinite N64 main loop in C++
            NativeBridge.nativeGameBoot(otrPath, assetManager);
        }).start();
    }
}
