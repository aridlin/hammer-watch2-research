# Public research scope

The public repository includes original analysis code, synthetic tests, sanitized
findings and hashes/acquisition instructions. It excludes APKs, SDK binaries,
vendor images, downloaded face packs, raw captures, credentials, account data,
serial numbers, real Bluetooth addresses and user photos. Vendor assets are not
relicensed or bundled. Debug Android signing defaults are public test values.

Some tests require locally acquired private samples and skip in a clean checkout.
The recorded full test count comes from the private analysis workspace, not a
claim that GitHub alone supplies proprietary fixtures or a working sensor runtime.

Public releases use a reviewed snapshot rather than publishing the original
workspace history. Earlier chronological reports describe the evidence at that
stage; STATUS.md identifies superseded hypotheses and present blockers.

Verification: 146 tests pass with local samples; the clean public snapshot passes
126 tests and skips 20 tests that require deliberately excluded private inputs.
