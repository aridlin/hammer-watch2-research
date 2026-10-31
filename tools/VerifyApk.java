// Offline signature verification using Google's apksig library. Does not establish publisher identity.
import com.android.apksig.ApkVerifier;
import java.io.File;
import java.security.MessageDigest;
import java.util.HexFormat;

public final class VerifyApk {
    public static void main(String[] args) throws Exception {
        if (args.length == 0) throw new IllegalArgumentException("Supply one or more APK files");
        boolean failed = false;
        System.out.print("[\n");
        for (int i = 0; i < args.length; i++) {
            File file = new File(args[i]);
            // Quote safely without third-party JSON dependencies.
            String name = file.getName().replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t");
            try {
                ApkVerifier.Result r = new ApkVerifier.Builder(file).build().verify();
                System.out.print("  {\"file\":\"" + name + "\",\"verified\":" + r.isVerified()
                    + ",\"v2\":" + r.isVerifiedUsingV2Scheme() + ",\"v3\":" + r.isVerifiedUsingV3Scheme()
                    + ",\"error_count\":" + r.getAllErrors().size() + ",\"warning_count\":" + r.getWarnings().size()
                    + ",\"signer_certificate_sha256\":[");
                int n = 0;
                for (var cert : r.getSignerCertificates()) {
                    if (n++ > 0) System.out.print(",");
                    System.out.print("\"" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(cert.getEncoded())) + "\"");
                }
                System.out.print("]}");
                failed |= !r.isVerified();
            } catch (Exception e) {
                System.out.print("  {\"file\":\"" + name + "\",\"verified\":false,\"error\":\"" + e.getClass().getSimpleName() + "\"}");
                failed = true;
            }
            System.out.println(i == args.length - 1 ? "" : ",");
        }
        System.out.println("]");
        if (failed) System.exit(2);
    }
}
