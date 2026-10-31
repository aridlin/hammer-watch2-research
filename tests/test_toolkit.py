import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

import pytest
from tools import hammer_re as h


def archive(path, entries):
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries: z.writestr(name, data)
    return path


def test_inventory_known_bytes(tmp_path):
    p=tmp_path/'sample.bin';p.write_bytes(bytes(range(256)))
    r=h.inventory(p)
    assert r['size']==256 and r['entropy_bits_per_byte']==8
    assert r['sha256']==hashlib.sha256(p.read_bytes()).hexdigest()
    assert 'ascii_strings' not in r


def test_empty(tmp_path):
    p=tmp_path/'empty';p.touch()
    assert h.inventory(p)['entropy_bits_per_byte']==0
    assert h.compare(p,p)['same_offset_similarity']==1


def test_strings_and_signatures(tmp_path):
    p=tmp_path/'sample';p.write_bytes(b'\0\x89PNG\r\n\x1a\nHello World!\0')
    r=h.inventory(p,True)
    assert r['signatures']==[{'candidate':'png','offset':1}]
    assert r['ascii_strings'][0]['text']=='Hello World!'


def test_capture_strings_forbidden(tmp_path):
    p=tmp_path/'log';p.write_bytes(b'btsnoop\0secret-text')
    with pytest.raises(ValueError):h.inventory(p,True)


def test_compare_ranges_and_append(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.write_bytes(b'abcdef');b.write_bytes(b'aXXdeZQ')
    r=h.compare(a,b)
    assert r['different_ranges']==[{'start':1,'end_exclusive':3},{'start':5,'end_exclusive':7}]
    assert r['same_offset_equal_bytes']==3 and r['different_or_missing_bytes']==4
    assert h.compare(b,a)['different_ranges']==r['different_ranges']


def test_compare_truncation_and_chunk_boundary(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';a.write_bytes(b'A'*65538);b.write_bytes(b'A'*65535+b'BBB')
    assert h.compare(a,b)['different_ranges']==[{'start':65535,'end_exclusive':65538}]
    a.write_bytes(b'ababab');b.write_bytes(b'acacac')
    r=h.compare(a,b,1)
    assert r['range_count']==3 and r['ranges_truncated']


@pytest.mark.parametrize('name',['../escape','/absolute','x/../../escape','C:/drive','a\\b'])
def test_path_escape_rejected(tmp_path,name):
    p=archive(tmp_path/'bad.zip',[(name,b'x')]);out=tmp_path/'out'
    with pytest.raises(ValueError):h.extract(p,out)
    assert not out.exists()


def test_symlink_rejected(tmp_path):
    p=tmp_path/'bad.zip'
    with zipfile.ZipFile(p,'w') as z:
        e=zipfile.ZipInfo('link');e.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(e,'/tmp')
    with pytest.raises(ValueError):h.extract(p,tmp_path/'out')


def test_duplicate_rejected(tmp_path):
    p=archive(tmp_path/'bad.zip',[('A',b'1'),('a',b'2')])
    with pytest.raises(ValueError):h.extract(p,tmp_path/'out')


def test_extract_preserves_and_refuses_overwrite(tmp_path):
    p=archive(tmp_path/'ok.zip',[('x/',b''),('x/data',b'\0abc\xff')]);before=p.read_bytes();out=tmp_path/'out'
    h.extract(p,out)
    assert (out/'x/data').read_bytes()==b'\0abc\xff' and p.read_bytes()==before
    with pytest.raises(ValueError):h.extract(p,out)


def test_size_count_and_ratio_limits(tmp_path,monkeypatch):
    p=archive(tmp_path/'large.zip',[('data',b'abcd')])
    monkeypatch.setattr(h,'MAX_MEMBER',3)
    with pytest.raises(ValueError):h.extract(p,tmp_path/'out')
    monkeypatch.setattr(h,'MAX_MEMBER',256)
    monkeypatch.setattr(h,'MAX_ENTRIES',0)
    with pytest.raises(ValueError):h.extract(p,tmp_path/'out')
    monkeypatch.setattr(h,'MAX_ENTRIES',100)
    monkeypatch.setattr(h,'MAX_RATIO',0.5)
    with pytest.raises(ValueError):h.extract(p,tmp_path/'out')


def test_truncated_zip(tmp_path):
    p=tmp_path/'bad.zip';p.write_bytes(b'PK\x03\x04')
    with pytest.raises(zipfile.BadZipFile):h.extract(p,tmp_path/'out')


def test_corrupt_crc_cleans_staging(tmp_path):
    p=archive(tmp_path/'crc.zip',[('x',b'UNIQUE-CONTENT')]);p.write_bytes(p.read_bytes().replace(b'UNIQUE-CONTENT',b'CORRUPTCONTENT'))
    with pytest.raises(zipfile.BadZipFile):h.extract(p,tmp_path/'out')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.hammer-extract-*'))


def test_nested_bundle_and_manifest_requirement(tmp_path,monkeypatch):
    monkeypatch.setattr(h,'android_identity',lambda raw:{'status':'unavailable'})
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('AndroidManifest.xml',b'manifest');z.writestr('classes.dex',b'dex\n')
    p=archive(tmp_path/'bundle.xapk',[('base.apk',data.getvalue())])
    r=h.inspect_apk(p)
    assert r['kind']=='apk_bundle' and r['split_certificate_consistency']=='unverified'
    assert r['apks'][0]['dex']==['classes.dex']
    bad=archive(tmp_path/'bad.apk',[('x',b'x')])
    with pytest.raises(ValueError):h.inspect_apk(bad)


def test_nested_aggregate_limit(tmp_path,monkeypatch):
    monkeypatch.setattr(h,'android_identity',lambda raw:{'status':'unavailable'})
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:z.writestr('AndroidManifest.xml',b'abc')
    p=archive(tmp_path/'bundle.xapk',[('a.apk',data.getvalue()),('b.apk',data.getvalue())])
    monkeypatch.setattr(h,'MAX_ENTRIES',2)
    # Each child fits separately, total child member count also fits at 2.
    assert h.inspect_apk(p)['kind']=='apk_bundle'
    monkeypatch.setattr(h,'MAX_ENTRIES',1)
    with pytest.raises(ValueError):h.inspect_apk(p)


def test_cli_errors_json_and_no_overwrite(tmp_path):
    p=tmp_path/'empty';p.touch();out=tmp_path/'result.json'
    cmd=[sys.executable,'-m','tools.hammer_re','--output',str(out),'inventory',str(p)]
    assert subprocess.run(cmd,capture_output=True).returncode==0
    assert json.loads(out.read_text())['size']==0
    r=subprocess.run(cmd,capture_output=True,text=True)
    assert r.returncode==2 and json.loads(r.stderr)['type']=='FileExistsError'
    r=subprocess.run([sys.executable,'-m','tools.hammer_re','apk-inspect',str(p)],capture_output=True,text=True)
    assert r.returncode==2 and json.loads(r.stderr)['type']=='BadZipFile'


@pytest.mark.parametrize('magic',[b'btsnoop\0',b'\xd4\xc3\xb2\xa1',b'\x0a\x0d\x0d\x0a'])
def test_capture_headers_redacted_even_when_renamed(tmp_path,magic):
    p=tmp_path/'renamed.bin';p.write_bytes(magic+b'private content')
    assert h.inventory(p)['header_hex'] is None
    with pytest.raises(ValueError):h.inventory(p,True)


@pytest.mark.real_samples
def test_real_android_bundle():
    p=Path('private/apks/hammer-app.xapk')
    if not p.exists():pytest.skip('Real APK bundle not acquired')
    pytest.importorskip('androguard')
    r=h.inspect_apk(p)
    assert r['split_certificate_consistency']=='consistent' and r['package_consistency'] is True
    assert len(r['apks'])==20
    identity=r['apks'][0]['identity']
    assert identity['package']=='com.hammerup.app' and identity['version_name']=='1.0.15'
    assert identity['certificate_sha256']==['d6b2b309f5dec12e2e3e7d5f811c6157650dd82b52a2fcfeca220939bd7c6a03']
