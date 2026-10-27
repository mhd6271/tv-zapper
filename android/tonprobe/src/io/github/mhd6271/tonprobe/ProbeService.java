package io.github.mhd6271.tonprobe;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioPlaybackCaptureConfiguration;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.IBinder;
import android.util.Log;

/** Nimmt je 8 s auf (Wiedergabe-Mitschnitt, Mikrofon, Standard-Quelle) und meldet die Lautstaerke im logcat. */
public class ProbeService extends Service {
    @Override
    public int onStartCommand(Intent i, int f, int id) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("p", "Tonprobe", NotificationManager.IMPORTANCE_LOW));
        startForeground(1, new Notification.Builder(this, "p").setSmallIcon(android.R.drawable.ic_media_play)
                .setContentTitle("Tonprobe").build());
        int code = i.getIntExtra("code", 0);
        Intent data = i.getParcelableExtra("data");
        new Thread(() -> run(code, data)).start();
        return START_NOT_STICKY;
    }

    private void run(int code, Intent data) {
        sleep(4000);   // Fernsehbild wieder vorn
        AudioFormat fmt = new AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(16000)
                .setChannelMask(AudioFormat.CHANNEL_IN_MONO).build();
        try {
            MediaProjection mp = getSystemService(MediaProjectionManager.class).getMediaProjection(code, data);
            AudioPlaybackCaptureConfiguration cfg = new AudioPlaybackCaptureConfiguration.Builder(mp)
                    .addMatchingUsage(AudioAttributes.USAGE_MEDIA).addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
                    .addMatchingUsage(AudioAttributes.USAGE_GAME).build();
            measure("Wiedergabe-Mitschnitt", new AudioRecord.Builder().setAudioFormat(fmt)
                    .setAudioPlaybackCaptureConfig(cfg).build());
            mp.stop();
        } catch (Exception e) {
            Log.i("Tonprobe", "Wiedergabe-Mitschnitt: Fehler " + e);
        }
        for (int src : new int[]{MediaRecorder.AudioSource.DEFAULT, MediaRecorder.AudioSource.MIC,
                MediaRecorder.AudioSource.REMOTE_SUBMIX}) {
            try {
                measure("Quelle " + src, new AudioRecord.Builder().setAudioFormat(fmt).setAudioSource(src).build());
            } catch (Exception e) {
                Log.i("Tonprobe", "Quelle " + src + ": Fehler " + e);
            }
        }
        Log.i("Tonprobe", "fertig");
        stopSelf();
    }

    private void measure(String name, AudioRecord rec) {
        if (rec.getState() != AudioRecord.STATE_INITIALIZED) {
            Log.i("Tonprobe", name + ": nicht initialisiert");
            rec.release();
            return;
        }
        short[] buf = new short[1600];
        rec.startRecording();
        StringBuilder levels = new StringBuilder();
        long total = 0;
        for (int k = 0; k < 80; k++) {   // 80 x 0,1 s
            int n = rec.read(buf, 0, buf.length);
            double sum = 0;
            for (int j = 0; j < Math.max(n, 0); j++) sum += (double) buf[j] * buf[j];
            int rms = n > 0 ? (int) Math.sqrt(sum / n) : -1;
            total += Math.max(rms, 0);
            if (k % 8 == 0) levels.append(rms).append(' ');
        }
        rec.stop();
        rec.release();
        Log.i("Tonprobe", name + ": mittlere Lautstaerke " + (total / 80) + " (Verlauf " + levels + ")");
    }

    private static void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ignored) {
        }
    }

    @Override
    public IBinder onBind(Intent i) {
        return null;
    }
}
