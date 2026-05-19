package com.bkawrapper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import android.os.ParcelFileDescriptor;
import android.util.Log;

import androidx.core.app.NotificationCompat;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public class OtrService extends Service {

    private static final String TAG             = "OtrService";
    private static final String CHANNEL_ID      = "OtrServiceChannel";
    private static final int    NOTIFICATION_ID = 1;

    private static final String SENTINEL_FILENAME = "extraction_complete";

    public static final String ACTION_OTR_PROGRESS = "OTR_PROGRESS";
    public static final String ACTION_OTR_COMPLETE = "OTR_COMPLETE";
    public static final String ACTION_OTR_ERROR    = "OTR_ERROR";

    private long lastNotificationTime = 0;

    static {
        System.loadLibrary("bkawrapper");
    }

    private native void runNativeOtrGeneration(Object callback, int romFd, String outDir, String manifestPath);

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;

        String uriString = intent.getStringExtra("uri");
        String outDir    = intent.getStringExtra("outDir");
        String version   = intent.getStringExtra("version");

        if (version == null || version.isEmpty()) {
            version = "us"; 
        }
        final String finalVersion = version;

        startForeground(NOTIFICATION_ID,
            new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Preparing Banjo-Kazooie Assets")
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build());

        new Thread(() -> {
            try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(Uri.parse(uriString), "r")) {

                if (pfd == null) {
                    throw new Exception("Could not open ROM file descriptor.");
                }

                int fd = pfd.getFd();
                Log.i(TAG, "ROM fd established: " + fd);

                // RESTORED: Move the manifest out of the APK assets folder into internal storage for C++ to read
                String manifestName = "manifest_" + finalVersion + ".bin";
                File internalManifest = new File(getFilesDir(), manifestName);
                copyAssetToDisk(manifestName, internalManifest);

                // Pass the actual file path into the native generator
                runNativeOtrGeneration(this, fd, outDir, internalManifest.getAbsolutePath());

                writeSentinel(outDir);
                Log.i(TAG, "Extraction complete — broadcasting OTR_COMPLETE");
                LocalBroadcastManager.getInstance(this).sendBroadcast(new Intent(ACTION_OTR_COMPLETE));

            } catch (Exception e) {
                Log.e(TAG, "Extraction failed", e);
                Intent err = new Intent(ACTION_OTR_ERROR);
                err.putExtra("message", e.getMessage());
                LocalBroadcastManager.getInstance(this).sendBroadcast(err);
            } finally {
                stopForeground(true);
                stopSelf();
            }
        }, "BKA-ExtractionThread").start();

        return START_NOT_STICKY;
    }

    public void onProgressUpdate(int percent, String status) {
        updateOtrProgress(percent, status);
    }

    public void updateOtrProgress(int percent, String status) {
        Intent intent = new Intent(ACTION_OTR_PROGRESS);
        intent.putExtra("percent", percent);
        intent.putExtra("status",  status);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);

        long now = System.currentTimeMillis();
        if (now - lastNotificationTime >= 500 || percent == 100 || percent == 0) {
            lastNotificationTime = now;

            Notification notification =
                new NotificationCompat.Builder(this, CHANNEL_ID)
                    .setContentTitle("Extracting Banjo-Kazooie Assets")
                    .setContentText(percent + "% — " + status)
                    .setSmallIcon(android.R.drawable.stat_sys_download)
                    .setProgress(100, percent, false)
                    .setOngoing(true)
                    .build();

            NotificationManager mgr = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (mgr != null) mgr.notify(NOTIFICATION_ID, notification);
        }
    }

    private void copyAssetToDisk(String assetName, File outFile) throws IOException {
        if (outFile.exists()) {
            outFile.delete();
        }

        try (InputStream in = getAssets().open(assetName);
             OutputStream out = new FileOutputStream(outFile)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            Log.i(TAG, "Manifest extracted to filesystem: " + outFile.getAbsolutePath());
        }
    }

    private void writeSentinel(String outDir) {
        try {
            File sentinel = new File(outDir, SENTINEL_FILENAME);
            if (!sentinel.exists()) {
                sentinel.createNewFile();
            }
        } catch (Exception e) {
            Log.w(TAG, "Could not write sentinel: " + e.getMessage());
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "Asset Extraction Service",
                NotificationManager.IMPORTANCE_LOW);
            NotificationManager mgr = getSystemService(NotificationManager.class);
            if (mgr != null) mgr.createNotificationChannel(channel);
        }
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
