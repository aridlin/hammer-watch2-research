# Watch-face formats and capability limits

> Status note, 2026-10-31: sections record successive investigation stages.
> Physical uploads and digital seconds are now verified. Custom compass refresh
> remains broken; original factory compass works. See STATUS.md for current scope.


Updated 2026-10-31. Actual ADVENTURER source and official-app compiled BIN are now available. Earlier generic-reference findings below are historical; the latest target results are summarized here.

ADVENTURER uses the same observed 44-byte header / 38-byte resource index and CRC32 container, with 128 resources. Its `ats3089C` source has explicit compass, altitude and air-pressure widgets. All non-JSON resources survive the digital edit byte-for-byte. The offline vendor compiler exactly reproduces the acquired original. See [target acquisition](reports/adventurer-acquisition.json) and [candidate validation](reports/adventurer-digital-validation.json).

## Observed source packs

Twelve dial ZIPs were inspected: ten from the pinned iOS SDK and two additional Android SDK assets. One additional downloaded archive, `titan.zip`, contains unrelated OTA resources and was excluded from face parsing. It has not been flashed, repacked or treated as a face.

The source packs contain `firmware/dial.json` and raster resources, sometimes wrapped in a named root directory. Some also contain `firmware/file.json` and `app/` configuration. Apple metadata entries occur in several archives; they are preserved on extraction but excluded from face discovery. [Sample hashes and summary](reports/creek-sample-summary.json).

Observed `dial.json` keys include `frame_version`, `dial_version`, `name`, `dial_type`, `resolution_ratio`, `platform`, `preview`, `enable_pic_compress`, `item` and `fade_item`. Item dictionaries use `widget`, `type`, coordinates/dimensions, resource references, font or array directories, and additional options. These are observations from samples, not an exhaustive schema.

Examples include image glyph directories, text widgets for `time`, `hour` and `min`, day/week/month arrays, battery arrays and other data fields. The `fade_item` collection appears to describe a dim/AOD layout, consistent with SDK face categories; actual display behavior has not been tested.

`S6L8UQJij6O78LFmcwr03gykzn02.zip` from the Android demo declares `ats3085s`, `weather`, `altitude`, and `altitude_unit`. The altitude text entry uses x=92, y=350, w=80, h=24. Most other samples declare `ats3085c`. These declarations must be preserved when inspecting references; renaming them does not prove ATS3089C compatibility.

## Working parser and intermediate representation

`python -m tools.creek_face inspect FILE.zip` exports:

- Full decoded `dial.json`, preserving unknown keys and item dictionaries.
- Original JSON bytes in base64 plus SHA-256 for exact restoration.
- Widget/type counts per layer and member sizes/CRC32 values for nearby assets.
- Explicit unverified-HAMMER-compatibility status.

`restore-json` verifies the original-byte hash, rejects a changed decoded document, and writes the original metadata into a new file. This tests lossless inspection, **not** binary compilation. All ten main SDK packs have real-sample metadata round-trip tests. Generic extraction preserves all other source members.

The parser does not yet resolve every font/image reference, decode proprietary compressed resources, simulate data bindings, render a face, or compile a BIN. Source ZIP reconstruction and a compiled BIN encoder are different tasks.

## Desired factory-face capability matrix

| Feature | Reference evidence | HAMMER custom-face status |
|---|---|---|
| Digital hours/minutes | Multiple real Creek packs have digital-time declarations | Promising; runtime interpretation and 24-hour setting unverified |
| Battery | Reference packs include `battery` / `batarray` | Binding exists in references; target unverified |
| Weather | Additional Android sample declares weather text/array items | Binding exists in references; target unverified |
| Altitude | Additional Android sample declares altitude text and unit array | Binding exists in references; target unverified |
| Live compass | Actual ADVENTURER has ten `compass` widgets plus calibration hint | Source bindings preserved; physical runtime pending |
| Barometric pressure | Actual ADVENTURER has `air_pressure` text and pointer | Source bindings preserved; physical runtime pending |
| Other complications | Steps, calorie, heart and other declarations appear in samples | Verify individually on matching firmware |

This table describes declarations, not successful sensor readings. Static graphics cannot substitute for live compass, pressure, weather or altitude bindings.

## Observed compiled BIN container

The offline SDK 10.7 harness produced two genuine compiler outputs. Their source packs declare `ats3085c`; they are **reference binaries, not verified HAMMER binaries**. Both pass the following container model, unchanged reconstruction, and unchanged JSON replacement tests. A repeat compilation also returned identical bytes. [Compiler evidence](reports/sdk-compiler-results.json).

| Offset | Size | Observed meaning |
|---:|---:|---|
| 0 | 30 | NUL-padded face name bytes |
| 30 | 4 | Little-endian magic `0x5AA54321` |
| 34 | 1 | Dial category |
| 35 | 2 | Little-endian dial version |
| 37 | 2 | Little-endian resource count |
| 39 | 1 | Compression marker; 4 in both outputs |
| 40 | 4 | Little-endian CRC32/ISO-HDLC of **all bytes from offset 44 to EOF** |
| 44 | count × 38 | Resource index |

Each 38-byte index entry is a 30-byte NUL-padded name followed by little-endian 32-bit absolute offset and byte size. The index CRC covers index and payload, not the first 44 header bytes. `dial.json` and `file.json` are stored as readable JSON; most resource image bodies have been transformed from their original PNG/BMP encodings.

`tools.creek_bin` checks magic, CRC, table bounds and non-overlapping ranges. Its JSON IR stores original header/index bytes, separate resource/gap/trailing segments and inspection metadata. `rebuild` reassembles these segments and requires the original hash. Unknown bytes are retained rather than guessed.

`replace-json` is an explicit offline edit: it validates the replacement as a JSON object, splices the selected member, updates affected absolute offsets/length and recalculates the CRC. Replacing a member with identical bytes returns the exact original container. Resizing a JSON member has tests showing that other resource payloads remain unchanged. This is not installation validation.

## Observed image resources

In the tested compression-4 containers, images begin with a four-byte little-endian bitfield: low five bits are a format marker, width occupies bits 10–20, and height bits 21–31. Bits 5–9 were zero in observed images. The remaining bytes are a raw LZ4 block, without an embedded uncompressed-size prefix.

- Marker **24** decodes to width × height × 4 bytes in **BGRA** order. All **147** such resources from both binaries matched the original reference PNG pixels exactly after channel conversion, including colored assets that distinguish BGRA from RGBA.
- Marker **4** decodes to width × height × 2 bytes, little-endian **RGB565**. Two resources decoded. The background's raw RGB565 bytes matched quantization of its source bitmap; the preview was regenerated by the SDK and is not asserted identical to its old source preview.

The image decoder enforces supported markers, dimensions and decompressed size. Raw extraction preserves encoded members even when the filename says `.png` or `.bmp`; `decode-image` produces viewable PNGs. Other compression/format combinations remain unsupported, not guessed.

## Target-watch reconstruction gates

The app's AOT implementation contains `DialTool.encode`, `encodeActRes` and `CrcCheck.calculateUint8List`; addresses are recorded in [AOT index](reports/aot-method-index.json). The SDK oracle ran the JX_3085C path. A native image-packing plugin was unavailable in the x86 lab, so other platform modes remain untested.

Before claiming the requested face works:

1. Obtain the factory face reference and at least two downloadable resources for the actual HAMMER firmware/device ID and framework version. Check them against the observed variant rather than assume a match.
2. If the factory face is firmware-resident, locate its renderer/resources offline. Determine whether downloadable resources expose the same dynamic bindings.
3. Modify only the clock elements after the actual target layout is known, preserving original bindings and immutable recovery resources.
4. Check 00:00, 09:05, 12:00 and 23:59, leading zeros and AOD in the eventual renderer/device. A formatted host time string is not watch validation.
5. Defer physical installation and live compass/altitude/pressure checks to the final version, as the user requested. No physical watch was accessed during this lab stage.

## Actual hardware installation — 2026-10-31

The real firmware accepted the separately named, vendor-compiled digital resource
and reports it active. Original ADVENTURER remains present. Both binary and JSON
names use ewr24digital; all127 non-layout resources are unchanged. Header/body CRC,
rolling transfer checksum, real data offsets and the post-install inquiry were
verified. Runtime visual and sensor behavior remains a separate pending acceptance
step. See [physical result](reports/physical-installation-validation.json).

## Additional image marker and source edits

Marker 12 is opaque BGR888 with LZ4 in the acquired factory background: decoding
matches every RGB source pixel. Markers 4/16 and 24 remain RGB565 and BGRA paths.
`tools.adventurer_source` performs bounded deterministic bitmap edits and generates
numeric month arrays using existing digit glyphs. Revision 4 keeps factory pointer
pivots/ranges, dims hour/minute/hub RGB to 24%, and replaces the 32×288 seconds
sprites with an 11-pixel segment near radius 225. The compiler preserves reviewed
pixels; RGB565 AOD comparisons use decoded quantized original pixels. JSON/image
checks do not establish live firmware rendering or sensor refresh.

## Weather-font and Polish date variants

Revisions 5/6 retain source pointer pivots and the outer ADVENTURER compass model.
Weather Time glyphs are copied exactly, with 48×58 digits and a 20×58 colon.
Weekday bitmaps use a full transparent 466×466 array canvas with lettering placed
on the lower inner arc. Native day data feeds the curved renderer; lower-arc glyphs
are preflipped for upright orientation. Runtime position/order is still an explicit
hardware acceptance check, not established by compiler success. The weather
source contains day and curved widgets separately; this combination is new.

Revision 6 uses Monday-first Polish labels, verified against the actual weather
array order. DejaVu Sans Bold Oblique supplies letters unavailable in the original
English weekday bitmaps. Numeric date and time retain actual weather glyphs.

Revision 7 makes the weather clock subtly smaller: digits 47×57 instead of 48×58,
colon 20×57 instead of 20×58. The 322-pixel combined time remains centered on x233.
Weekday bitmap baseline radius increases from 130 to 138; native numeric date
radius stays 138. Native compass/pointer bindings remain identical to revision 6.
The separate candidate name preserves `ewrcompass_` and `@LC` as a naming hypothesis,
without changing the original entry or asserting a firmware naming rule.

## Sci-Fi Timer orange edit

Official source `CWR05G_23612` declares `ats3085s`, dial type 6, with theme resources
outside `firmware` under `app/color_picture`. The orange variant is the original
`#B87F44/background_0_0565.bmp`; no orange palette is guessed or substituted.
Bitmap slogans are removed by fixed masks, with exact pixel preservation outside
those masks/corner-clock mask. Weekday arrays remain seven 56×20 RGBA images.
The retained time/date/battery/activity font resource hashes are unchanged.

The corner compass copies the weather face's native ring, scale, compass_icon,
angle text, compass_pos and calibration-hint widget structure, with coordinates
translated and explicit orange coloring. This preserves native sensor binding
intent; compilation does not establish functioning compass updates on hardware.

The final compiled container is 143,415 bytes with 126 resources, valid CRC32, and
1,459,304 total decoded image bytes (not peak firmware RAM). A static preview is
composited from real assets with fixed illustrative values; it is not a renderer
or sensor emulator. Local `.hface` distribution wraps this BIN with a bounded,
signed manifest; see mobile-installer.md for that independent package format.
