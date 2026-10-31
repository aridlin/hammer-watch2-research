# Face resources

Proprietary samples and generated vendor assets stay under ignored `faces/local/`.

Actual official-app downloads now include ADVENTURER (`ewrcompass_0819@LC`,
`ats3089C`, two palettes) and Modular Compact-Weather (`ewr01_compass_4`).
Their source ZIPs and compiled BINs are retained under `local/adventurer/`.

`local/adventurer/vendor-digital-orange.bin` is the offline vendor-compiled
ADVENTURER digital candidate. It is not a hardware-validated final face.
`local/adventurer/digital-orange/` holds the Python-produced binary, readable JSON
and checks. All 127 non-layout resources are preserved. The original analog
preview assets remain stale. No physical installation or live test has occurred.

Earlier generic SDK reference packs remain useful comparisons; their platform
labels must not substitute for actual target evidence. See [status](../STATUS.md)
and [validation](../reports/adventurer-digital-validation.json).

The preferred physical-test input is now **`local/adventurer/ewr24digital.bin`**,
a separately named vendor-compiled face with original multi-palette selection.
It preserves the factory filename/entry and all 127 non-layout resource hashes.
Earlier same-name and forced-color variants are diagnostic artifacts. No physical
upload or rendering acceptance has occurred. See the prepared plan and STATUS.md.

The real watch has now accepted and activated `ewr24digital.bin` after explicit
approval. Original ADVENTURER remains present. This supersedes the earlier
"no physical upload" status; visual and live-complication acceptance is pending.
