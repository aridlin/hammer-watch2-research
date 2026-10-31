import json,zipfile
from pathlib import Path
import pytest
from tools.package_face import create_package,DOMAIN


def test_signed_package_matches_bounded_face_and_signature(tmp_path):
    binary=Path('faces/local/scifi/modified-final.bin')
    if not binary.exists():pytest.skip('Private face binary absent')
    rsa=pytest.importorskip('cryptography.hazmat.primitives.asymmetric.rsa')
    from cryptography.hazmat.primitives import serialization,hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);path=tmp_path/'private.pem'
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));path.chmod(0o600)
    destination=tmp_path/'face.hface';report=create_package(binary,path,destination,'Sci-Fi orange PL','CWR05G_23612.bin')
    assert report['signed']
    with zipfile.ZipFile(destination) as z:
        assert set(z.namelist())=={'manifest.json','face.bin','signature.bin'}
        metadata=z.read('manifest.json');data=z.read('face.bin');signature=z.read('signature.bin')
        key.public_key().verify(signature,DOMAIN+len(metadata).to_bytes(4,'big')+metadata+data,padding.PKCS1v15(),hashes.SHA256())
        assert data==binary.read_bytes() and json.loads(metadata)['filename']=='CWR05G_compassPL01.bin'
        with pytest.raises(Exception):key.public_key().verify(signature,DOMAIN+len(metadata).to_bytes(4,'big')+metadata+data+b'x',padding.PKCS1v15(),hashes.SHA256())
    with pytest.raises(FileExistsError):create_package(binary,path,destination,'title','CWR05G_23612.bin')
    path.chmod(0o644)
    with pytest.raises(ValueError):create_package(binary,path,tmp_path/'other.hface','title','CWR05G_23612.bin')
