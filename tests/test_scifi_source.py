from pathlib import Path
import json
import pytest
from tools.scifi_source import NAME,LABELS,TEXT_MASKS,CLOCK_ELLIPSE,transform
from tools.creek_bin import parse,decode_image
from tools.face_budget import image_budget
ROOT=Path('faces/local/scifi')


def samples():
    if not (ROOT/'modified-final.bin').exists():pytest.skip('Private official Sci-Fi source/compiler samples absent')
    return (ROOT/'original.bin').read_bytes(),(ROOT/'modified-final.bin').read_bytes()


def test_scifi_original_functional_widgets_retained_except_corner_clock():
    old,new=samples();a=parse(old);b=parse(new)
    model=lambda r:next(e['json'] for e in r['resources'] if e['name']=='dial.json')
    weather=json.loads((ROOT/'weather-source/firmware/dial.json').read_text())
    assert model(b)==transform(model(a),weather) and b['name']==NAME
    assert [x for x in model(a)['item'] if x.get('widget')=='text']==[x for x in model(b)['item'] if x.get('widget')=='text' and x.get('type') not in {'angle','compass_pos'}]
    assert model(a)['fade_item']==model(b)['fade_item']
    assert not any(x.get('widget')=='pointer' for x in model(b)['item'])
    assert [x['type'] for x in model(b)['item'][-6:]]==['other','other','compass_icon','angle','compass_pos','compass_hint']


def test_scifi_small_resources_and_exact_unchanged_clock_fonts():
    old,new=samples();a=parse(old);b=parse(new);before={e['name']:e['sha256'] for e in a['resources']};after={e['name']:e['sha256'] for e in b['resources']}
    changed={n for n in before if before[n]!=after[n]}
    assert changed=={'dial.json','background_0_0565.bmp',*(f'Week_{i}_8888.png' for i in range(7))}
    assert len(after.keys()-before.keys())==24
    assert image_budget(new)['decoded_image_bytes_sum']==1459304
    for i in range(7):assert decode_image(new,f'Week_{i}_8888.png').size==(56,20)
    assert LABELS==('pon','wt','śr','czw','pt','sob','ndz')


def test_scifi_orange_source_pixel_edits_are_strictly_bounded():
    samples();Image=pytest.importorskip('PIL.Image');ImageDraw=pytest.importorskip('PIL.ImageDraw')
    original=Image.open(ROOT/'source/app/color_picture/#B87F44/background_0_0565.bmp').convert('RGB')
    edited=Image.open(ROOT/'clean-orange-pl-compass-source-v2/firmware/background_0_0565.bmp').convert('RGB')
    allowed=Image.new('L',(466,466));draw=ImageDraw.Draw(allowed)
    for l,t,r,b in TEXT_MASKS.values():draw.rectangle((l,t,r-1,b-1),fill=255)
    draw.ellipse(CLOCK_ELLIPSE,fill=255)
    for a,b,mask in zip(original.get_flattened_data(),edited.get_flattened_data(),allowed.get_flattened_data()):
        if mask:assert b==(0,0,0)
        else:assert a==b
