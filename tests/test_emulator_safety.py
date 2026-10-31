from pathlib import Path
import pytest
from tools.watch_emulator import validate_transport


@pytest.mark.parametrize('value',['android-netsim','android-netsim:localhost:35447','android-netsim:127.0.0.1:35447'])
def test_virtual_radio_only_accepts_local_netsim(value):
    assert validate_transport(value)==value


@pytest.mark.parametrize('value',['usb:0','hci-socket:0','android-netsim:remote-host:22','android-netsim:localhost:0','android-netsim:localhost:65536','android-netsim:localhost:1234,usb=0'])
def test_physical_and_remote_transports_are_rejected(value):
    with pytest.raises(ValueError):validate_transport(value)


def test_adb_wrapper_pins_emulator_and_separate_server():
    script=Path('tools/adb-debug').read_text()
    assert 'adb -P 5038 -s emulator-5580' in script


def test_compiler_harness_contains_no_radio_or_upload_calls():
    source=Path('lab/android/app/src/main/java/local/hammer/compiler/MainActivity.java').read_text()
    assert 'manager.upload' not in source and 'manager.initSDK(' not in source
    manifest=Path('lab/android/app/src/main/AndroidManifest.xml').read_text()
    for permission in ['INTERNET','BLUETOOTH','BLUETOOTH_ADMIN','BLUETOOTH_SCAN','BLUETOOTH_CONNECT','BLUETOOTH_ADVERTISE']:
        assert f'android.permission.{permission}" tools:node="remove"' in manifest


def test_reference_compiler_rejects_wrong_platform_and_symlinks(tmp_path):
    import json
    from tools.sdk_compile_reference import validate_source
    (tmp_path/'firmware').mkdir()
    p=tmp_path/'firmware/dial.json'
    p.write_text(json.dumps({'platform':'ats3089c','resolution_ratio':'466x466'}))
    with pytest.raises(ValueError):validate_source(tmp_path)
    p.write_text(json.dumps({'platform':'ats3085c','resolution_ratio':'466x466'}))
    assert validate_source(tmp_path)[0]==tmp_path.resolve()
    (tmp_path/'link').symlink_to('/tmp')
    with pytest.raises(ValueError):validate_source(tmp_path)


def test_duplicate_virtual_peer_lock_rejected_and_released(tmp_path):
    from tools.watch_emulator import exclusive_peer
    path=tmp_path/'peer.lock'
    with exclusive_peer(path):
        with pytest.raises(ValueError):
            with exclusive_peer(path):pass
    with exclusive_peer(path):pass
