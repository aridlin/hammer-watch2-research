from pathlib import Path
import copy,json,math
import pytest
from tools.scifi_fullscreen import transform,coordinate,dimension,NAME,SCALE
from tools.creek_bin import parse,decode_image
from tools.face_budget import image_budget
ROOT=Path('faces/local/scifi')


def test_geometry_keeps_background_full_size_and_binding_semantics():
    base={'name':'CWR05G_compassPL01','platform':'ats3085s','resolution_ratio':'466x466',
          'item':[{'widget':'icon','type':'background','x':0,'y':0,'w':466,'h':466,'picture':'background_0_0565.bmp'},
                  {'widget':'text','type':'time','x':68,'y':238,'w':246,'h':82,'font':'Time','min_numwidth':5}],
          'fade_item':[]}
    saved=copy.deepcopy(base);after=transform(base)
    assert base==saved and after['name']==NAME and after['name']!=base['name']
    assert after['item'][0]==base['item'][0]
    assert after['item'][1]['w']==4*64+25 and after['item'][1]['h']==93
    assert after['item'][1]['type']=='time' and after['item'][1]['font']=='Time'


def test_compiled_fullscreen_layout_and_pixels():
    path=ROOT/'fullscreen-pl02.bin';source=ROOT/'clean-orange-pl-compass-source-v2/firmware/dial.json'
    if not path.exists() or not source.exists():pytest.skip('Private face samples absent')
    old=json.loads(source.read_text());data=path.read_bytes();report=parse(data)
    new=next(r['json'] for r in report['resources'] if r['name']=='dial.json')
    assert new==transform(old) and report['name']==NAME and report['crc_valid']
    for layer in ('item','fade_item'):
        assert len(old[layer])==len(new[layer])
        for a,b in zip(old[layer],new[layer]):
            geometry={'x','y','w','h','centerx','centery'}
            assert {k:v for k,v in a.items() if k not in geometry}=={k:v for k,v in b.items() if k not in geometry}
            if b.get('widget') in {'text','array'}:
                x,y,w,h=(b[k] for k in ('x','y','w','h'))
                assert max(math.hypot(px-233,py-233) for px in (x,x+w-1) for py in (y,y+h-1))<232
    image=decode_image(data,'background_0_0565.bmp').convert('RGB')
    for point in [(233,0),(0,233),(465,233),(233,465)]:
        r,g,b=image.getpixel(point);assert r>g+20 and g>b+15
    assert image.getpixel((coordinate(341),coordinate(135)))==(0,0,0)
    assert decode_image(data,'Time_0_8888.png').size==(64,93)
    assert decode_image(data,'Week_5_8888.png').size==(64,23)
    assert image_budget(data)['decoded_image_bytes_sum']<1800000


def test_scaled_compiled_fonts_are_exact_source_images():
    path=ROOT/'fullscreen-pl02.bin';source=ROOT/'fullscreen-pl02-final-source/firmware'
    if not path.exists() or not source.exists():pytest.skip('Private full-display sources absent')
    Image=pytest.importorskip('PIL.Image');data=path.read_bytes()
    for relative in ['Time/Time_0_8888.png','Data/Data_8_8888.png','Week/Week_5_8888.png','Compass_ring_8888.png']:
        with Image.open(source/relative) as image:
            assert decode_image(data,Path(relative).name).convert('RGBA').tobytes()==image.convert('RGBA').tobytes()
