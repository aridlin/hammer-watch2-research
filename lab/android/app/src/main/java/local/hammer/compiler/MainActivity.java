package local.hammer.compiler;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import com.example.mylibrary.CreekManager;
import com.example.proto.Enums;
import java.io.File;
import java.nio.file.Files;
import kotlin.Unit;

/** Offline vendor-compiler oracle. No upload, pairing, auth, or initSDK call. */
public final class MainActivity extends Activity {
    private TextView status;
    private void status(String value) {
        runOnUiThread(() -> status.setText(value));
        try { Files.write(new File(getFilesDir(), "status.txt").toPath(), value.getBytes(java.nio.charset.StandardCharsets.UTF_8)); }
        catch (Exception error) { android.util.Log.e("HammerCompilerLab", "status write failed", error); }
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        status = new TextView(this);
        status.setPadding(24, 48, 24, 24);
        status.setTextSize(20);
        setContentView(status);
        File source = new File(getFilesDir(), "input");
        if (!new File(source, "firmware/dial.json").isFile()) {
            status("Missing input/firmware/dial.json. Push a reference source pack; then restart this activity.");
            return;
        }
        String selected = getIntent().getStringExtra("platform");
        final Enums.Platform platform;
        if (selected == null || selected.equals("JX_3085C_PLATFORM")) {
            platform = Enums.Platform.JX_3085C_PLATFORM;
        } else if (selected.equals("JX_3085S_PLATFORM")) {
            platform = Enums.Platform.JX_3085S_PLATFORM;
        } else {
            status("Platform selection failed: unsupported offline oracle");
            return;
        }
        status("Starting isolated SDK compiler...");
        CreekManager manager = CreekManager.Companion.getSInstance();
        manager.creekRegister(this, () -> {
            status("Parsing reference pack as " + platform.name() + "; target compatibility unverified.");
            manager.parseDial(source.getAbsolutePath(), 466, 466, 233,
                platform, model -> {
                    status("Reference parsed. Encoding offline...");
                    manager.encodeDial(bytes -> {
                        try {
                            File output = new File(getFilesDir(), "reference.bin");
                            Files.write(output.toPath(), bytes);
                            status("Encoded reference.bin: " + bytes.length + " bytes. No upload attempted.");
                        } catch (Exception error) {
                            status("Encoding output failed: " + error.getClass().getSimpleName());
                        }
                        return Unit.INSTANCE;
                    });
                    return Unit.INSTANCE;
                });
            return Unit.INSTANCE;
        });
    }
}
