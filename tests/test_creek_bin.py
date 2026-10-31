import base64
import json
from pathlib import Path
import struct
import zlib
import pytest
from tools.creek_bin import parse,export_ir,rebuild,replace_json,extract,decode_image


def container(resources):
    head=bytearray(44);head[:4]=b'test';struct.pack_into('<I',head,30,0x5AA54321)
    head[34]=6;struct.pack_into('<H',head,37,len(resources));head[39]=4
    index=bytearray();payload=bytearray();offset=44+38*len(resources)
    for name,raw in resources:
        index.extend(struct.pack('<30sII',name.encode(),offset,len(raw)))
        payload.extend(raw);offset+=len(raw)
    result=head+index+payload;struct.pack_into('<I',result,40,zlib.crc32(result[44:]));return bytes(result)


def test_parse_and_lossless_ir_with_gap_and_trailing():
    b=container([('dial.json',b'{"unknown":1}'),('raw',b'\0\xff')])+b'trailing'
    b=bytearray(b);struct.pack_into('<I',b,40,zlib.crc32(b[44:]));b=bytes(b)
    r=parse(b);assert r['resource_count']==2 and r['resources'][0]['json']=={'unknown':1}
    assert rebuild(export_ir(b))==b
    ir=export_ir(b);ir['segments'][0]['offset']+=1
    with pytest.raises(ValueError):rebuild(ir)


def test_resize_json_preserves_other_resources():
    b=container([('dial.json',b'{}'),('font',bytes(range(100)))])
    changed=replace_json(b,'dial.json',b'{"new":{"nested":true}}')
    r=parse(changed);font=r['resources'][1]
    assert r['crc_valid'] and r['resources'][0]['json']['new']=={'nested':True}
    assert changed[font['offset']:font['offset']+font['size']]==bytes(range(100))
    assert replace_json(b,'dial.json',b'{}')==b
    with pytest.raises(ValueError):replace_json(b,'font',b'{}')
    with pytest.raises(ValueError):replace_json(b,'dial.json',b'[]')


def test_bad_crc_truncation_and_overlap():
    b=container([('dial.json',b'{}'),('font',b'abc')])
    with pytest.raises(ValueError):parse(b[:-1])
    with pytest.raises(ValueError):parse(b'\0'*44)
    corrupt=bytearray(b);corrupt[-1]^=1
    with pytest.raises(ValueError):parse(corrupt)
    assert not parse(corrupt,verify_crc=False)['crc_valid']
    struct.pack_into('<I',corrupt,44+38+30,44+76)
    struct.pack_into('<I',corrupt,40,zlib.crc32(corrupt[44:]))
    with pytest.raises(ValueError):parse(corrupt)


@pytest.mark.parametrize('name',['../escape','/absolute','C:/drive','x\\y'])
def test_resource_extraction_path_policy(tmp_path,name):
    b=container([(name,b'a')])
    with pytest.raises(ValueError):extract(b,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_extract_raw_resources(tmp_path):
    b=container([('dial.json',b'{}'),('font',b'raw')]);extract(b,tmp_path/'out')
    assert (tmp_path/'out/font').read_bytes()==b'raw'
    with pytest.raises(FileExistsError):extract(b,tmp_path/'out')


def test_bgra_and_rgb565_image_decoding():
    block=pytest.importorskip('lz4.block');pytest.importorskip('PIL')
    for marker,pixels in [(24,b'\0\0\xff\xff'),(4,b'\0\xf8'),(12,b'\0\0\xff')]:
        raw=struct.pack('<I',marker|(1<<10)|(1<<21))+block.compress(pixels,store_size=False)
        b=container([('pixel',raw)])
        image=decode_image(b,'pixel')
        assert image.convert('RGB').getpixel((0,0))==(255,0,0)


@pytest.mark.real_samples
def test_sdk_compiled_binaries_roundtrip_and_image_pixels(tmp_path):
    cases=[('circlePhoto.sdk10.7.bin','compiler-source/circlePhoto/firmware',58),
           ('CW06G_TITAD101_01.sdk10.7.bin','compiler-source2/firmware',95)]
    if not all((Path('faces/local')/name).exists() for name,_,_ in cases):pytest.skip('SDK-produced binaries absent')
    Image=pytest.importorskip('PIL.Image');pytest.importorskip('lz4.block')
    decoded=0
    for name,source,count in cases:
        b=(Path('faces/local')/name).read_bytes();r=parse(b)
        assert r['resource_count']==count and r['crc_valid']
        assert rebuild(export_ir(b))==b
        e=next(e for e in r['resources'] if e['name']=='dial.json')
        raw=b[e['offset']:e['offset']+e['size']]
        assert replace_json(b,'dial.json',raw)==b
        changed=replace_json(b,'dial.json',json.dumps({**e['json'],'offline_test':True}).encode())
        assert parse(changed)['resources'][e['index']]['json']['offline_test'] is True
        for resource in r['resources']:
            if resource['name'].endswith('.json'):continue
            raw=b[resource['offset']:resource['offset']+resource['size']]
            if struct.unpack_from('<I',raw)[0]&31!=24:continue
            original=list((Path('faces/local')/source).rglob(resource['name']))
            assert original
            image=decode_image(b,resource['name'])
            with Image.open(original[0]) as source_image:
                assert image.tobytes()==source_image.convert('RGBA').tobytes()
            decoded+=1
    assert decoded==147


def test_bad_lz4_is_a_controlled_error():
    pytest.importorskip('lz4.block');pytest.importorskip('PIL')
    raw=struct.pack('<I',24|(1<<10)|(1<<21))+b'broken'
    with pytest.raises(ValueError):decode_image(container([('bad',raw)]),'bad')
