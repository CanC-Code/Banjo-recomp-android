package com.bkawrapper;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

public class MainActivity extends AppCompatActivity {
    private static final int PICK_ROM_REQUEST = 1001;

    private View menuOverlay;
    private View otrContainer;
    private ProgressBar progressBar;
    private TextView progressText;
    private TextView currentArtifactText;

    // The listener that catches updates from OtrService
    private final BroadcastReceiver progressReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            int percent = intent.getIntExtra("percent", 0);
            String status = intent.getStringExtra("status");
            updateUI(percent, status);
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

        // Note: nativeInit is now called by the OtrService itself
        new MenuController(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Start listening for progress updates when the app is visible
        LocalBroadcastManager.getInstance(this).registerReceiver(
                progressReceiver, new IntentFilter("OTR_PROGRESS"));
    }

    @Override
    protected void onPause() {
        super.onPause();
        // Stop listening when the app goes to background to save battery
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
            Uri uri = data.getData();
            startExtraction(uri);
        }
    }

    private void startExtraction(Uri romUri) {
        menuOverlay.setVisibility(View.GONE);
        otrContainer.setVisibility(View.VISIBLE);

        // Instead of a thread here, we start the Service
        Intent serviceIntent = new Intent(this, OtrService.class);
        serviceIntent.putExtra("uri", romUri.toString());
        serviceIntent.putExtra("outDir", getFilesDir().getAbsolutePath());
        startService(serviceIntent);
    }

    private void updateUI(int percent, String fileName) {
        // Broadcasts already run on the UI thread, but runOnUiThread is safe
        progressBar.setProgress(percent);
        progressText.setText(percent + "%");
        currentArtifactText.setText(fileName);

        if (percent >= 100) {
            currentArtifactText.setText("Extraction Complete!");
        }
    }
}
