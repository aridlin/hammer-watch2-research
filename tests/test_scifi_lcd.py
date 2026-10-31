import copy
import json
from pathlib import Path
import pytest
from tools.scifi_lcd import restyle, NAME
from tools.creek_bin import parse, decode_image


def test_compass_translation_preserves_bindings_and_relative_geometry():
    model = {'name':'CWR05G_compassPL02', 'item':[
        {'type':'compass_icon','x':352,'y':68,'picture':'Compass_angle_8888.png','enable_hidden':1},
        {'type':'angle','x':320,'y':98,'font':'Compass_data','unit_count':11},
        {'type':'time','x':45,'y':239,'font':'Time'}], 'fade_item':[]}
    before = copy.deepcopy(model)
    changed = restyle(model)
    assert model == before and changed['name'] == NAME
    assert changed['item'][2] == before['item'][2]
    for old,new in zip(before['item'][:2], changed['item'][:2]):
        assert (new['x']-old['x'],new['y']-old['y']) == (-10,-9)
        assert new['color'] == '#000000'
        assert {k:v for k,v in new.items() if k not in {'x','y','color'}} == {k:v for k,v in old.items() if k not in {'x','y','color'}}


def test_real_lcd_container_and_divider_joins():
    path = Path('faces/local/scifi/fullscreen-pl03.bin')
    previous = Path('faces/local/scifi/fullscreen-pl02.bin')
    if not path.exists() or not previous.exists():
        pytest.skip('Private compiled face samples absent')
    data = path.read_bytes(); report = parse(data)
    model = next(r['json'] for r in report['resources'] if r['name']=='dial.json')
    old = next(r['json'] for r in parse(previous.read_bytes())['resources'] if r['name']=='dial.json')
    assert report['crc_valid'] and model == restyle(old)
    image = decode_image(data,'background_0_0565.bmp').convert('RGB')
    # Previously abrupt endpoints now reach a shared boundary.
    for point in [(269,104),(270,104),(142,150),(142,168),(270,30),(440,169)]:
        assert image.getpixel(point) == (0,0,0)
    assert image.getpixel((345,112))[0] > 170  # no black compass badge
    for resource in report['resources']:
        if resource['name'].startswith('Compass_') and resource['name'].endswith('.png'):
            im = decode_image(data,resource['name']).convert('RGBA')
            assert all(lo==hi==0 for lo,hi in im.getextrema()[:3])


def test_balanced_compass_has_equal_divider_margins():
    path = Path('faces/local/scifi/fullscreen-pl04.bin')
    previous = Path('faces/local/scifi/fullscreen-pl02.bin')
    if not path.exists() or not previous.exists():
        pytest.skip('Private compiled face samples absent')
    report = parse(path.read_bytes())
    model = next(r['json'] for r in report['resources'] if r['name']=='dial.json')
    old = next(r['json'] for r in parse(previous.read_bytes())['resources'] if r['name']=='dial.json')
    assert report['crc_valid'] and model == restyle(old, balanced=True)
    ring = next(w for w in model['item'] if w.get('picture')=='Compass_ring_8888.png')
    assert ring['x']-270 == 169-(ring['y']+ring['h']) == 12
