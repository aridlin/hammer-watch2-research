# HAMMER Watch 2 watch-face research

Evidence-led reverse engineering of HAMMER Watch 2, its Android companion app
`com.hammerup.app`, Creek watch-face resources and Bluetooth transfers.

**Latest offline variant: full-screen orange Sci-Fi Timer, with readouts enlarged
14% and the drawn outer frames removed.** Import the signed
`Sci-Fi-Timer-Orange-PL-Fullscreen.hface` into the existing installer 0.2.
The original smaller face is preserved; this variant has not been installed or
validated on hardware. See [full-screen validation](reports/scifi-fullscreen-validation.json).

**Earlier deliverable (2026-10-31): orange Sci-Fi Timer with the side slogans and
SPORT arrows removed, Polish weekdays, and the corner analog clock replaced by
the weather face's native compass widgets.** Original main time/date/battery and
activity font assets are preserved. Normal-frame compass behavior and stability
remain unverified on a real watch.

A separately signed **Android installer APK (version 0.2)** is built locally in `dist/`, with the
face included. It reuses the recovered protocol, needs no HAMMER login/Internet,
and imports signed `.hface` packages for future faces. See
[mobile installer](mobile-installer.md), [face validation](reports/scifi-validation.json)
and [Android emulator tests](reports/installer-emulator-validation.json).
Vendor resources and built APKs are local artifacts, not committed to this repo.

Version 0.2 fixes rotation interrupting transfers and adds explicit, offset/CRC
verified recovery without overwriting. An interrupted transfer has now been
recovered using the user's phone; the user confirmed the face visible. The APK
update preserves app data, pairing, signing identity and face bytes.
[Phone recovery evidence](reports/installer-v02-phone-recovery.json).

Earlier ADVENTURER tests had slow/skipped updates and one reported reboot.
**Desktop live uploads remain suspended; the watch stays unpaired from the PC.**
The installer is an explicit user-controlled experimental client. Phone recovery
and face appearance are now confirmed; compass performance/stability are not. It rejects the earlier unstable ADVENTURER test packages.
The cropped ADVENTURER fix and three diagnostic controls remain offline only.
See [current status](STATUS.md), [research](research.md), [format](format.md) and
[protocol](protocol.md). Earlier sections below retain chronological evidence.

Public content contains original tooling, sanitized evidence and acquisition
instructions. APKs, vendor face assets/binaries, raw traffic, account material,
photos and physical device identifiers remain private and are excluded from Git.
Earlier investigation sections below are chronological records; STATUS.md takes
precedence over their historical missing-input or untested statements.

## Setup

Rebuilding revision 6 also requires the locally installed **DejaVu Sans Bold Oblique**
font for Polish weekday lettering. Proprietary time/day glyphs must be acquired
locally through the documented source workflow.

Python 3.11+ runs the generic tools with no dependencies. The recorded analysis environment uses Python 3.12.13, Androguard 4.1.3, pytest 8.4.2, JADX 1.5.6 and Google apksig 8.13.0. Java 17+ and `javac` are needed for the optional signature verifier; `nm` is needed for native export inspection.

```sh
UV_CACHE_DIR="$PWD/private/uv-cache" uv venv --python 3.12 .venv
UV_CACHE_DIR="$PWD/private/uv-cache" uv pip install --python .venv/bin/python -r requirements-analysis.lock
.venv/bin/python -m tools.hammer_re doctor
.venv/bin/python -m pytest -q
```

The lock file records exact installed package versions; it is not a hash-locked supply-chain attestation. Runtime dependencies are optional: use system Python for generic commands, or install the `android` extra from `pyproject.toml` for AXML/certificate extraction.

This managed workspace reserves an empty read-only `.git` directory. A working Git repository is initialized at `private/git`; use `./tools/git-project status`, `./tools/git-project diff`, and other normal Git arguments through that wrapper. The public snapshot uses ordinary Git; this wrapper is only for the original managed workspace.

## Acquire the same inputs

Private inputs, decompiled source, raw captures and generated local reports are excluded from version control. Public manifests contain pinned URLs, SHA-256 hashes and sizes. Never commit raw artifacts or unreviewed string dumps.

```sh
python -m tools.fetch_artifacts reports/acquisition-manifest.json
python -m tools.fetch_artifacts reports/creek-source-manifest.json
python -m tools.fetch_artifacts reports/creek-additional-source-manifest.json
```

The mirror APK bundle is approximately 191 MiB. The fetcher refuses existing mismatched files and changed downloads. The original acquisition used APKPure's `latest` URL; its manifest supplies a version-specific reacquisition URL. Mirror availability can change. All 20 acquired APK signatures verify, but publisher authenticity still requires a certificate comparison with a trusted Google Play installation.

Extract only into new destinations:

```sh
python -m tools.hammer_re extract private/apks/hammer-app.xapk --destination private/apks/hammer-app
python -m tools.hammer_re extract private/apks/hammer-app/com.hammerup.app.apk --destination private/apks/com.hammerup.app
python -m tools.hammer_re extract private/apks/hammer-app/config.arm64_v8a.apk --destination private/apks/config.arm64_v8a
python -m tools.hammer_re extract private/sources/jadx-1.5.6.zip --destination private/jadx
chmod u+x private/jadx/bin/jadx
```

The current workspace already contains these artifacts; do not repeat extraction into their existing directories.

## Inspect and compare

```sh
mkdir -p reports/local faces/local
.venv/bin/python -m tools.hammer_re --output reports/local/apk.json apk-inspect private/apks/hammer-app.xapk
python -m tools.hammer_re inventory private/apks/hammer-app/com.hammerup.app.apk
python -m tools.hammer_re compare sample-a.bin sample-b.bin
python -m tools.creek_face --output reports/local/source.json inspect private/sources/CreekSDK/Example/CreekSDK/circlePhoto.zip
python -m tools.creek_face restore-json reports/local/source.json --destination faces/local/original-dial.json
```

Reports refuse overwrite. `inventory` hashes and computes entropy over the entire file, scanning up to the first 8 MiB for signatures. Signature matches are candidates, not detected proprietary formats. `--strings` opts into bounded ASCII previews; capture strings and headers are suppressed for recognized capture formats. Store unreviewed output privately. `compare` reports differences at the same offsets without realigning insertions.

`creek_face` exports complete JSON documents, unknown fields, resource inventories and base64 originals. `restore-json` restores byte-identical original metadata and rejects edited IR. It does **not** compile a watch binary itself. The separate SDK harness compiles reference packs. Source ZIPs can also contain `app/` configuration and `firmware/file.json`; extraction preserves these, while the current IR focuses on `dial.json`.

Archive policy: 512 MiB input/aggregate uncompressed data, 256 MiB per member, 4,096 entries, ratio at most 1,000:1; nested APK budgets also aggregate. Absolute paths, parent traversal, backslashes, drive separators, links, special files, encrypted members and duplicate normalized paths are rejected. Extraction stages privately, validates CRCs while reading, and refuses an existing destination. This is an inspection tool, not an untrusted-code sandbox.

## Reproduce Android evidence

```sh
mkdir -p private/java
javac -cp private/sources/apksig-8.13.0.jar -d private/java tools/VerifyApk.java
java -Xmx1g -cp private/java:private/sources/apksig-8.13.0.jar VerifyApk private/apks/hammer-app/*.apk
python -m tools.static_recon private/apks/config.arm64_v8a/lib/arm64-v8a/libapp.so --resource-lib private/apks/config.arm64_v8a/lib/arm64-v8a/libcreekActRes.so --output reports/local/native.json
./tools/jadx-local -j 2 --no-res --single-class com.actions.actres.ActresPlugin --single-class-output private/analysis/ActresPlugin.java private/apks/hammer-app/com.hammerup.app.apk
```

`static_recon` searches a fixed allowlist of public identifiers and reports exact file offsets; it does not dump arbitrary secrets. Decompiled source is an approximation: verify important behavior against DEX instructions or native disassembly. JADX does not decompile Flutter's AOT Dart implementation.

## Inputs needed next

The user supplied **ADVENTURER** as the target and **model 2039 / firmware V2.0.12**. AOT tracing supports firmwareId 2039. Still needed: ADVENTURER's share link/resource, the watch-face framework (`plateVersion`) and matching downloaded samples. Do not include your account password, pairing secret, serial number or MAC address.

For stronger APK provenance, install [HAMMER App from Google Play](https://play.google.com/store/apps/details?id=com.hammerup.app), then use an already authorized ADB connection:

```sh
adb shell pm path com.hammerup.app
```

Pull **each returned APK path**, including all splits, into a new private directory with `adb pull`. This project has invoked ADB only against its dedicated debug emulator, never a physical phone. Non-root ADB generally cannot read a release app's private data directory; do not root, clear app data or reinstall to obtain samples. If face export is unavailable, we will select a focused capture procedure after identifying the device and relevant app flow.

No tool here connects to a physical watch, flashes firmware, alters bootloaders or bypasses watch signatures. The experimental radio peer uses only local Netsim. Physical installation and live-sensor validation remain deferred to the final version, as requested.

## Compiled BIN tools

The observed SDK 10.7 container and image formats now have real-sample tests. These reference binaries do not establish target-watch compatibility.

```sh
python -m tools.creek_bin inspect faces/local/circlePhoto.sdk10.7.bin --output reports/local/bin-inspection.json
python -m tools.creek_bin export-ir faces/local/circlePhoto.sdk10.7.bin --output reports/local/bin-ir.json
python -m tools.creek_bin rebuild reports/local/bin-ir.json --destination faces/local/rebuilt.bin
python -m tools.creek_bin extract faces/local/circlePhoto.sdk10.7.bin --destination faces/local/raw-members
.venv/bin/python -m tools.creek_bin decode-image faces/local/CW06G_TITAD101_01.sdk10.7.bin --name preview_0565.bmp --destination faces/local/decoded-preview.png
python -m tools.creek_bin replace-json faces/local/circlePhoto.sdk10.7.bin --name dial.json --replacement edited-dial.json --destination faces/local/edited-offline.bin
```

Extraction preserves raw resources: image names ending in `.png`/`.bmp` can hold proprietary compressed pixels. Use `decode-image` for viewable PNGs. Replacing JSON updates subsequent offsets and container CRC while retaining other resource bytes; it does not validate sensor semantics or installation. See [format.md](format.md).

## Authenticated reads and offline BLE inspection

The user previously completed sign-in in the official emulator app; as of 2026-10-31 that session is rejected as logged in elsewhere. A narrow read-only client now successfully retrieves the app's allowed Bluetooth names. Session files/responses must stay private; no CLI password input or login bypass is implemented. See [emulator.md](emulator.md) for usage. Face-list reads require verified firmware/framework/customer compatibility fields; these are still missing for the user's watch.

```sh
.venv/bin/python -m tools.creek_frame private/emulator/watch-hw2-corrected-events.jsonl --events
```

This prints recovered header fields only and omits payloads. It sends no commands and does not claim complete BLE framing or a working virtual watch.

## Synthetic virtual-device response mode

```sh
.venv/bin/python -m tools.watch_emulator --duration 180 \
  --synthetic-device-info --log private/emulator/new-trial.jsonl
.venv/bin/python -m tools.hci_summary private/emulator/synthetic-05.btsnoop
```

Response mode is experimental: the app receives notifications at Android's transport but still retries initialization. No completed pairing or face download is claimed. Model/version reflect user evidence; other fields are synthetic, with no claimed target dial framework. The default peer remains discovery-only. HCI summaries omit payloads and addresses. `observe_emulator_ble` is a failed/experimental attachment path, not a working dependency of the analysis. See [emulator.md](emulator.md).

Latest emulator result (2026-10-31): corrected response sequence routing advances
the unchanged official app to Pairing and subsequent setup commands. A limited
normal-binding virtual setup oracle is implemented; pairing completion and
catalog acquisition are still pending. The app requires renewed direct login.
See [current status](STATUS.md) and [sanitized evidence](reports/virtual-setup-progress.json).

## ADVENTURER acquired and digital candidate built — 2026-10-31

The latest results supersede earlier acquisition/pairing blockers: the virtual
watch paired successfully, and the official gallery downloaded ADVENTURER plus
a second real face. The isolated SDK reproduces the official ADVENTURER BIN
byte-for-byte. An orange digital candidate compiles with all 127 non-layout
resources preserved. Hardware installation, palette rendering, 24-hour firmware
behavior and live complications remain pending. [Current status](STATUS.md),
[acquisition](reports/adventurer-acquisition.json), [validation](reports/adventurer-digital-validation.json).

Reproduce the offline candidate after acquiring the private original:

```sh
.venv/bin/python -m tools.adventurer_digital \
  faces/local/adventurer/official-green.bin \
  --destination faces/local/adventurer/new-digital-orange --palette-index 1
```

This writes a candidate BIN, readable JSON and validation report to a new explicit
directory. It cannot install or transmit anything. The source archive already
contains orange assets; the tool does not recreate complications with a picture.

## Real watch connected; standalone test prepared — 2026-10-31

Read-only physical inquiries now confirm device2039 / firmware2.0.12, platform
SDK enum3, color72 and dial framework8. The installed face list includes the same
ADVENTURER name/version. Platform3 compilation reproduces the original byte-for-byte.
The official SDK's full original upload was validated against a virtual receiver,
including byte-identical stream reconstruction; physical uploads remain untested.

Prefer the separately named candidate with original palette metadata preserved:

```sh
.venv/bin/python -m tools.adventurer_digital \
  faces/local/adventurer/official-color72.bin \
  --destination faces/local/adventurer/new-standalone --standalone
.venv/bin/python -m tools.watch_face_install \
  --candidate faces/local/adventurer/ewr24digital.bin
```

The second command is **offline preparation only**. Physical execution requires
explicit flags and the exact reviewed hash, and is pending user approval.
See [current status](STATUS.md), [physical compatibility](reports/physical-compatibility.json)
and [prepared plan](reports/standalone-install-plan.json).

## Physical test face installed — 2026-10-31

Following explicit approval, the real watch accepted the separate
**`ewr24digital.bin`** test face and reports it active. Its original ADVENTURER
remains installed. A repeated-ACK handling issue was corrected; completion used
a checksum-verified continuation from180 bytes, without a new start packet.
**136 tests pass**, including the actual physical ACK trace. No firmware or
bootloader was changed. Actual appearance, HH:MM/24-hour behavior, compass,
altitude/pressure and AOD still require user observation.
[Installation evidence](reports/physical-installation-validation.json).
