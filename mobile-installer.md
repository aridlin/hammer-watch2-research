# Local Android watch-face installer

An unofficial, small native Android app built from the already recovered Creek
face-transfer protocol. It adds no cloud login and contains no vendor Android SDK.
The release APK is in the local `dist/` directory and includes the edited orange
Sci-Fi Timer face. Proprietary face assets/APKs and private signing keys are not
published in Git.

## Use

1. Install `dist/HAMMER-Face-Installer-0.1.apk` on an Android 8+ phone.
2. Ensure HW2 is paired in Android Bluetooth settings. Close/disconnect the
   official HAMMER app so it does not occupy the connection.
3. Open **HAMMER Face Installer**, allow Nearby devices when requested, select
   **Connect watch**, then **Apply face**. The included face loads automatically.
4. For future faces, choose **Import face** and select the project's signed
   `.hface` package; the APK does not need to change for each new face.

Keep the app open during transfer. It keeps the screen awake. A failed file
transfer is not automatically retried or resumed. A partial face can remain on the
watch; check its face list through the official app before another attempt.

This version supports the verified HW2 model 2039 / firmware 2.0.12 / platform 3 /
orange device color 72 / face framework 8 and LZ4 compression 4. It refuses other
profiles, existing destination filenames, full storage/slots, invalid checksums
and packages not signed for this installer. It does not erase, overwrite, activate
with an undocumented command, bind/unbind, flash firmware or send arbitrary files.
Only known device/dial/MTU inquiries and D1/D2/D4 face-transfer frames are used.

The included face is **experimental**. Emulator transport success does not verify
watch rendering, compass responsiveness or stability. The earlier unstable
ADVENTURER variants are explicitly rejected by the package importer. Desktop live
installation remains disabled. No real watch was used to test this app.

## Source and package format

The app is `lab/android/installer`, package `local.hammer.installer`. `Wire.java`
and `TransferSession.java` are pure Java and have host tests; the activity provides
Android pairing selection, GATT discovery/MTU/CCCD, file import and progress.

A `.hface` file is a bounded ZIP with exactly three entries:

- `manifest.json`: UTF-8 JSON with title, unique filename, SHA-256, source filename,
  explicit target profile and experimental status.
- `face.bin`: the validated Creek container (maximum 1 MiB).
- `signature.bin`: RSA2048/SHA-256 PKCS#1 v1.5 signature over the domain bytes
  `HAMMER-FACE-PACKAGE-v1\0`, the four-byte big-endian manifest length, manifest,
  then face bytes.

ZIP member allowlisting, size bounds, signature/hash verification and native
container range/CRC checks precede any device operation. Signed metadata cannot
change the fixed supported profile. The package signing public key is bundled;
private keys remain local. Keep the same private keys for compatible future APK
updates and face packages. This signature is our distribution layer; it is not a
bypass of any watch firmware signature.

## Rebuild

Use the repository's analysis environment plus the `installer` extra, a JDK and
Android SDK/Gradle versions described in emulator.md. The installer itself has no
vendor SDK dependency. In a fresh checkout, create keys once:

```sh
.venv/bin/python -m tools.installer_keys
```

Do not run key initialization over the existing directory. Acquire the Sci-Fi and
weather source packs legitimately through the official app; resource hashes are
recorded in reports/scifi-acquisition.json. Cached resource URLs carry temporary
signatures: those query strings are deliberately excluded from public research.
The public unsigned paths may refuse downloads.

Prepare and compile a face using the isolated compiler workflow:

```sh
.venv/bin/python -m tools.scifi_source \
  --source faces/local/scifi/source \
  --weather-source faces/local/scifi/weather-source \
  --destination faces/local/scifi/rebuild-source
.venv/bin/python -m tools.sdk_compile_reference \
  --source faces/local/scifi/rebuild-source \
  --destination faces/local/scifi/rebuild.bin \
  --platform JX_3085S_PLATFORM --abi arm64-v8a
.venv/bin/python -m tools.package_face \
  --binary faces/local/scifi/rebuild.bin \
  --key private/installer/face-signing.pem \
  --destination private/installer/assets/scifi-orange-pl-compass.hface \
  --title 'Sci-Fi Timer — Orange PL + Compass' \
  --origin-filename CWR05G_23612.bin
```

New destinations are required. Polish weekday generation uses the locally
installed DejaVu Sans Mono Bold Oblique font. Then build using the existing Gradle
executable with JAVA_HOME/ANDROID_HOME configured:

```sh
gradle -p lab/android :installer:assembleRelease :installer:lintRelease
```

The signed APK is `lab/android/installer/build/outputs/apk/release/installer-release.apk`.
`private/installer/assets` is the only local asset input for this module.

## Verification performed

- Release build succeeds; Android lint reports no issues.
- Google apksig verifies the APK signature; package inspection confirms no INTERNET
  permission, native vendor libraries, private signing keys or debuggable flag.
- Host Java tests cover exact container format, CRCs, compatibility checks,
  no-overwrite behavior, full transfer, delayed duplicate ACKs, and fragmented
  metadata with unrelated notifications interleaved.
- Two Android runtime tests pass: tampered package rejection and full GATT transfer
  to an exact-byte Netsim receiver, including duplicate notifications and final
  active-face confirmation. Received bytes independently match the packaged face.
- Instrumentation refuses non-emulator targets. Its fixed synthetic address and
  instrumentation APK are not in the distributed release app.

The simulator is a transport receiver, not watch firmware or a sensor emulator.
See reports/installer-emulator-validation.json and reports/installer-apk-signature.json.
