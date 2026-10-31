import json,shutil,stat
import pytest
from tools import installer_keys


def test_local_key_generation_is_private_and_never_replaces_keys(tmp_path,monkeypatch):
    keytool=shutil.which('keytool')
    if not keytool:pytest.skip('JDK keytool unavailable')
    pytest.importorskip('cryptography')
    monkeypatch.setattr(installer_keys,'ROOT',tmp_path)
    target=tmp_path/'private/installer';result=installer_keys.initialize(target,keytool)
    assert result['keys_created'] and not result['private_values_printed']
    for name in ['face-signing.pem','signing.properties','app-release.keystore']:
        assert stat.S_IMODE((target/name).stat().st_mode)==0o600
    assert not (target/'temporary-password').exists()
    original=(target/'face-signing.pem').read_bytes()
    with pytest.raises(FileExistsError):installer_keys.initialize(target,keytool)
    assert (target/'face-signing.pem').read_bytes()==original
    with pytest.raises(ValueError):installer_keys.initialize(tmp_path/'public',keytool)
