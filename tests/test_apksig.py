import json
from pathlib import Path
import struct
import subprocess
import zipfile
import pytest


@pytest.mark.real_samples
def test_apksig_detects_real_apk_tampering(tmp_path):
    base=Path('private/apks/hammer-app/com.hammerup.app.apk')
    jar=Path('private/sources/apksig-8.13.0.jar')
    if not (base.exists() and jar.exists()):pytest.skip('APK or Google apksig absent')
    subprocess.run(['javac','-cp',str(jar),'-d',str(tmp_path),'tools/VerifyApk.java'],check=True,capture_output=True)
    command=['java','-Xmx1g','-cp',str(tmp_path)+':'+str(jar),'VerifyApk']
    good=subprocess.run(command+[str(base)],capture_output=True,text=True)
    assert good.returncode==0 and json.loads(good.stdout)[0]['verified']
    raw=bytearray(base.read_bytes())
    with zipfile.ZipFile(base) as z:
        e=z.getinfo('assets/flutter_assets/AssetManifest.json')
        name_len,extra_len=struct.unpack_from('<HH',raw,e.header_offset+26)
        position=e.header_offset+30+name_len+extra_len+2
        raw[position]^=1
    bad=tmp_path/'tampered.apk';bad.write_bytes(raw)
    result=subprocess.run(command+[str(bad)],capture_output=True,text=True)
    assert result.returncode==2 and json.loads(result.stdout)[0]['verified'] is False
