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
    private static final String CHANNEL_ID = "OtrServiceChannel";
    private static final int NOTIFICATION_ID = 1;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "OTR Service", NotificationManager.IMPORTANCE_LOW);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(channel);
        }
    }

    public void updateOtrProgress(int percent, String status) {
        Intent intent = new Intent("OTR_PROGRESS");
        intent.putExtra("percent", percent);
        intent.putExtra("status", status);
        LocalBroadcastManager.getInstance(this).sendBroadcast(intent);

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Extracting Assets...")
                .setContentText(percent + "% - " + status)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setProgress(100, percent, false)
                .build();
        
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) manager.notify(NOTIFICATION_ID, notification);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String uriString = intent.getStringExtra("uri");
        String outDir = intent.getStringExtra("outDir");

        startForeground(NOTIFICATION_ID, new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Starting Extraction")
                .setSmallIcon(android.R.drawable.stat_sys_download).build());

        new Thread(() -> {
            try {
                Uri uri = Uri.parse(uriString);
                ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r");
                
                if (pfd != null) {
                    // FIX: detachFd() is compatible with API 26+
                    int fd = pfd.detachFd(); 
                    Log.i("OtrService", "Detached FD: " + fd);
                    
                    NativeBridge.nativeInit(this);
                    NativeBridge.runOtrGeneration(fd, getAssets(), outDir);
                }
            } catch (Exception e) {
                Log.e("OtrService", "Extraction Error", e);
            } finally {
                stopForeground(true);
                stopSelf();
            }
        }).start();

        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
