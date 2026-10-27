package io.github.mhd6271.tonprobe;

import android.app.Activity;
import android.content.Intent;
import android.media.projection.MediaProjectionManager;
import android.os.Bundle;

public class ProbeActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (checkSelfPermission("android.permission.RECORD_AUDIO") != 0) {
            requestPermissions(new String[]{"android.permission.RECORD_AUDIO"}, 1);
        } else {
            ask();
        }
    }

    @Override
    public void onRequestPermissionsResult(int c, String[] p, int[] r) {
        ask();
    }

    private void ask() {
        startActivityForResult(getSystemService(MediaProjectionManager.class).createScreenCaptureIntent(), 2);
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        android.util.Log.i("Tonprobe", "Freigabe: " + (res == RESULT_OK ? "ja" : "nein (" + res + ")"));
        startForegroundService(new Intent(this, ProbeService.class).putExtra("code", res).putExtra("data", data));
        finish();
    }
}
