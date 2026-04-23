package com.bkawrapper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.ParcelFileDescriptor;
import android.net.Uri;
import androidx.core.app.NotificationCompat;
import androidx.localbroadcastmanager.content.LocalBroadcastManager;
import android.util.Log;

public class OtrService extends Service {
    private static final String TAG = "OtrService";
    private static final String CHANNEL_ID = "OtrServiceChannel";
    private static final int NOTIFICATION_ID = 1;

    // Intent Actions
    public static final String ACTION_OTR_PROGRESS = "OTR_PROGRESS";
    public static final String ACTION_OTR_COMPLETE = "OTR_COMPLETE";
    public static final String ACTION_OTR_ERROR = "OTR_ERROR";

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "Asset Extraction Service", NotificationManager.IMPORTANCE_LOW);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    /**
     * Called by C++ via JNI (NativeBridge) to update the UI
     */
    public void updateOtrProgress(int percent, String status) {
        // 1. Send broadcast to update the ProgressBar in MainActivity
        Intent intent = new Intent(ACTION_OTR_PROGRESS);
        intent.putExtra("percent", percent);
        intent.putExtra("status", status);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);

        // 2. Update the system notification
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Extracting Banjo-Kazooie Assets")
                .setContentText(percent + "% - " + status)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setProgress(100, percent, false)
                .setOngoing(true)
                .build();

        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) manager.notify(NOTIFICATION_ID, notification);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;

        String uriString = intent.getStringExtra("uri");
        String outDir = intent.getStringExtra("outDir");

        // Start as a foreground service immediately to prevent the OS from killing us
        startForeground(NOTIFICATION_ID, new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Preparing Extraction")
                .setSmallIcon(android.R.drawable.stat_sys_download).build());

        new Thread(() -> {
            try {
                Uri uri = Uri.parse(uriString);
                ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r");

                if (pfd != null) {
                    // Detach the FD so C++ code owns the file handle
                    int fd = pfd.detachFd(); 
                    Log.i(TAG, "ROM File Descriptor detached: " + fd);

                    // Initialize JNI bridge and run extraction (this blocks until done)
                    NativeBridge.nativeInit(this);
                    NativeBridge.runOtrGeneration(fd, getAssets(), outDir);

                    // --- EXTRACTION FINISHED SUCCESSFULLY ---
                    Log.i(TAG, "Extraction complete. Sending OTR_COMPLETE signal.");
                    LocalBroadcastManager.getInstance(this).sendBroadcast(new Intent(ACTION_OTR_COMPLETE));
                } else {
                    throw new Exception("Could not open ROM file descriptor.");
                }
            } catch (Exception e) {
                Log.e(TAG, "Extraction Failed", e);
                Intent errorIntent = new Intent(ACTION_OTR_ERROR);
                errorIntent.putExtra("message", e.getMessage());
                LocalBroadcastManager.getInstance(this).sendBroadcast(errorIntent);
            } finally {
                // Cleanup service
                stopForeground(true);
                stopSelf();
            }
        }).start();

        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
