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

public class OtrService extends Service {

    private static final String TAG             = "OtrService";
    private static final String CHANNEL_ID      = "OtrServiceChannel";
    private static final int    NOTIFICATION_ID = 1;

    private static final String SENTINEL_FILENAME = "extraction_complete";

    public static final String ACTION_OTR_PROGRESS = "OTR_PROGRESS";
    public static final String ACTION_OTR_COMPLETE = "OTR_COMPLETE";
    public static final String ACTION_OTR_ERROR    = "OTR_ERROR";

    static {
        System.loadLibrary("bkawrapper");
    }

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

        startForeground(NOTIFICATION_ID,
            new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Preparing Banjo-Kazooie Assets")
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .build());

        new Thread(() -> {
            try {
                Uri uri = Uri.parse(uriString);
                ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r");

                if (pfd == null) {
                    throw new Exception("Could not open ROM file descriptor.");
                }

                int fd = pfd.detachFd();
                Log.i(TAG, "ROM fd detached: " + fd);

                NativeBridge.nativeInit(this);
                
                boolean success = NativeBridge.runOtrGeneration(fd, getAssets(), outDir);

                if (success) {
                    writeSentinel(outDir);
                    Log.i(TAG, "Extraction complete — broadcasting OTR_COMPLETE");
                    LocalBroadcastManager.getInstance(this).sendBroadcast(new Intent(ACTION_OTR_COMPLETE));
                } else {
                    throw new Exception("OTR Generation failed: Manifest missing or invalid format.");
                }

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

    @Override
    public IBinder onBind(Intent intent) { return null; }

    public void updateOtrProgress(int percent, String status) {
        Intent intent = new Intent(ACTION_OTR_PROGRESS);
        intent.putExtra("percent", percent);
        intent.putExtra("status",  status);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);

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

    private void writeSentinel(String outDir) {
        try {
            File sentinel = new File(outDir, SENTINEL_FILENAME);
            if (!sentinel.exists()) {
                sentinel.createNewFile();
            }
            Log.i(TAG, "Sentinel written: " + sentinel.getAbsolutePath());
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
}
