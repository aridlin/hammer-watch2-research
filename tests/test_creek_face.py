import base64
import json
from pathlib import Path
import zipfile
import pytest
from tools.creek_face import inspect_source,restore_json


def test_source_ir_preserves_unknown_and_roundtrip(tmp_path):
    p=tmp_path/'face.zip'
    raw=b'{ "platform": "unknown", "unknown_vendor_field": [9,8], "item": [{"type":"time", "widget":"text"}] }\n'
    with zipfile.ZipFile(p,'w') as z:
        z.writestr('sample/firmware/dial.json',raw);z.writestr('sample/firmware/Time/digit.png',b'fake')
    r=inspect_source(p)
    assert r['documents'][0]['document']['unknown_vendor_field']==[9,8]
    assert r['documents'][0]['layers']['item']['types']=={'time':1}
    ir=tmp_path/'ir.json';ir.write_text(json.dumps(r));out=tmp_path/'restored.json'
    restore_json(ir,out)
    assert out.read_bytes()==raw
    with pytest.raises(FileExistsError):restore_json(ir,out)
    r['documents'][0]['document']['platform']='modified';ir.write_text(json.dumps(r))
    with pytest.raises(ValueError):restore_json(ir,tmp_path/'changed')


def test_missing_and_invalid_json(tmp_path):
    p=tmp_path/'bad.zip'
    for raw in [b'[]',b'{',b'{"item": 1}',b'{"item":[null]}']:
        with zipfile.ZipFile(p,'w') as z:z.writestr('firmware/dial.json',raw)
        with pytest.raises(ValueError):inspect_source(p)
    with zipfile.ZipFile(p,'w') as z:z.writestr('x','x')
    with pytest.raises(ValueError):inspect_source(p)


@pytest.mark.real_samples
def test_real_creek_samples(tmp_path):
    root=Path('private/sources/CreekSDK/Example/CreekSDK')
    samples=[p for p in sorted(root.glob('*.zip')) if p.name!='titan.zip']
    if not samples:pytest.skip('Real vendor samples not acquired')
    assert len(samples)==10
    for p in samples:
        r=inspect_source(p)
        with zipfile.ZipFile(p) as z:
            for d in r['documents']:
                assert base64.b64decode(d['original_json_base64'])==z.read(d['member'])
                assert json.loads(z.read(d['member']))==d['document']
        ir=tmp_path/(p.stem+'.ir.json');ir.write_text(json.dumps(r))
        for index,d in enumerate(r['documents']):
            out=tmp_path/(p.stem+f'.{index}.restored.json')
            restore_json(ir,out,index)
            assert out.read_bytes()==base64.b64decode(d['original_json_base64'])
