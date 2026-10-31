from pathlib import Path
import json
import pytest
from tools.adventurer_digital import transform,METER_TYPES,METER_PICTURES
from tools.adventurer_source import clean_meter_background,PATCH_PATHS,NORMAL_BOXES,GAUGE_BOXES
from tools.creek_bin import parse,decode_image


def test_seconds_no_meters_layout_preserves_compass_and_aod_cadence():
    source=Path('faces/local/adventurer/source/firmware/dial.json')
    if not source.exists():pytest.skip('Private source absent')
    original=json.loads(source.read_text());model,changes=transform(original,standalone=True,revision=3)
    assert model['name']=='ewr24dig03'
    assert not any(x.get('type') in METER_TYPES or x.get('picture') in METER_PICTURES for x in model['item'])
    assert [x for x in original['item'] if x.get('widget')=='compass']==[x for x in model['item'] if x.get('widget')=='compass']
    assert len([x for x in model['item'] if x.get('type')=='second' and x.get('widget')=='text'])==1
    assert not any(x.get('type')=='second' for x in model['fade_item'])
    clock=next(x for x in model['item'] if x.get('type')=='time')
    second=next(x for x in model['item'] if x.get('type')=='second')
    colon=next(x for x in model['item'] if x.get('picture')=='Time_10_8888.png')
    assert clock['x']+clock['w']==colon['x'] and colon['x']+colon['w']==second['x']
    assert clock['y']==colon['y']==second['y']
    assert (clock['x']+second['x']+second['w'])/2==233


def test_real_compiled_images_and_protected_compass_pixels():
    root=Path('faces/local/adventurer');candidate=root/'ewr24dig03.bin';original=root/'official-green.bin'
    if not candidate.exists() or not original.exists():pytest.skip('Private revision3 compiler output absent')
    old=original.read_bytes();new=candidate.read_bytes();a=parse(old);b=parse(new)
    changed={x['name'] for x,y in zip(a['resources'],b['resources']) if x['sha256']!=y['sha256']}
    assert changed=={'dial.json',*PATCH_PATHS}
    for name in PATCH_PATHS:
        before=decode_image(old,name).convert('RGB');after=decode_image(new,name).convert('RGB')
        assert after.tobytes()==clean_meter_background(before,name).tobytes()
        for y in range(466):
            for x in range(466):
                if (x-233)**2+(y-233)**2>=169**2:
                    assert before.getpixel((x,y))==after.getpixel((x,y))
        if name=='bg_0888.bmp':
            assert all(min(after.getpixel((x,y)))<180 for l,t,r,d in NORMAL_BOXES for y in range(t,d) for x in range(l,r))
        else:
            assert all(after.getpixel((x,y))==(0,0,0) for l,t,r,d in GAUGE_BOXES for y in range(t,d) for x in range(l,r))


def test_real_bgr888_decoder_exact_source_pixels():
    root=Path('faces/local/adventurer');original=root/'official-green.bin';source=root/'source/firmware/bg_0888.bmp'
    if not source.exists() or not original.exists():pytest.skip('Private real background absent')
    Image=pytest.importorskip('PIL.Image')
    with Image.open(source) as im:
        assert decode_image(original.read_bytes(),'bg_0888.bmp').tobytes()==im.convert('RGB').tobytes()
