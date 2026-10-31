from pathlib import Path
import shutil,subprocess
import pytest

def test_native_installer_protocol_on_host_java(tmp_path):
    javac=shutil.which('javac');java=shutil.which('java')
    if not javac or not java:pytest.skip('Host JDK not available')
    source=Path('lab/android/installer/src/main/java/local/hammer/installer')
    result=subprocess.run([javac,'-d',str(tmp_path),str(source/'Wire.java'),str(source/'TransferSession.java'),'tests/java/InstallerProtocolTest.java'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    samples=[str(p) for p in [Path('faces/local/scifi/original.bin'),Path('faces/local/scifi/modified-final.bin')] if p.exists()]
    result=subprocess.run([java,'-cp',str(tmp_path),'InstallerProtocolTest',*samples],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert result.stdout.startswith('PASS:')
