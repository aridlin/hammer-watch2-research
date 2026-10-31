import hashlib
import io
from pathlib import Path
from unittest.mock import patch
import pytest
from tools.fetch_artifacts import fetch
from tools.static_recon import recon


def record(raw=b'sample'):
    return {'path':'private/sample','url':'https://raw.githubusercontent.com/example/pinned/data',
            'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def test_fetch_verified_and_idempotent(tmp_path):
    with patch('tools.fetch_artifacts.urlopen',return_value=io.BytesIO(b'sample')):
        assert fetch(record(),tmp_path)['status']=='downloaded_and_verified'
    assert fetch(record(),tmp_path)['status']=='already_verified'
    assert (tmp_path/'private/sample').read_bytes()==b'sample'


def test_fetch_rejects_hash_and_path(tmp_path):
    with patch('tools.fetch_artifacts.urlopen',return_value=io.BytesIO(b'wrong')):
        with pytest.raises(ValueError):fetch(record(),tmp_path)
    assert list((tmp_path/'private').iterdir())==[]
    for path in ['../escape','private/../escape','/absolute','other/data']:
        r=record();r['path']=path
        with pytest.raises(ValueError):fetch(r,tmp_path)
    r=record();r['url']='http://raw.githubusercontent.com/a'
    with pytest.raises(ValueError):fetch(r,tmp_path)


def test_fetch_symlink_escape(tmp_path):
    (tmp_path/'private').mkdir();(tmp_path/'outside').mkdir()
    (tmp_path/'private/link').symlink_to(tmp_path/'outside',target_is_directory=True)
    r=record();r['path']='private/link/sample'
    with pytest.raises(ValueError):fetch(r,tmp_path)


def test_selected_static_strings(tmp_path):
    p=tmp_path/'lib.so';p.write_bytes(b'\0dial.json\0PRIVATE-SECRET\0')
    r=recon(p)
    assert r['observations']==[{'literal':'dial.json','file_offset':1}]
    assert 'PRIVATE-SECRET' not in str(r)
