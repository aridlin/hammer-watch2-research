from pathlib import Path
import json
import pytest
from tools.face_budget import image_budget
from tools.adventurer_source import revision7_images,revision8_images
from tools.adventurer_digital import transform
ROOT=Path('faces/local/adventurer')

def test_weekday_crop_preserves_exact_display_pixels_and_positions():
    if not (ROOT/'comparison-weather.bin').exists():pytest.skip('Private samples absent')
    Image=pytest.importorskip('PIL.Image')
    before=revision7_images(ROOT/'source');after=revision8_images(ROOT/'source')
    model,_=transform(json.loads((ROOT/'source/firmware/dial.json').read_text()),standalone=True,revision=8)
    widget=next(x for x in model['item'] if x.get('type')=='week')
    assert (widget['x'],widget['y'],widget['w'],widget['h'])==(181,338,61,33)
    for i in range(7):
        name=f'WWeek/WWeek_{i}_8888.png';restored=Image.new('RGBA',(466,466))
        restored.paste(after[name],(widget['x'],widget['y']))
        assert restored.tobytes()==before[name].tobytes()
    assert 7*61*33*4==56364


def test_real_binary_budget_exposes_weekday_expansion():
    weather=ROOT/'comparison-weather.bin';latest=ROOT/'ewrcompass_24d07@LC.bin'
    if not weather.exists() or not latest.exists():pytest.skip('Private samples absent')
    a=image_budget(weather.read_bytes());b=image_budget(latest.read_bytes())
    assert sum(x['decoded_pixel_bytes'] for x in a['weekday_images'])==56448
    assert sum(x['decoded_pixel_bytes'] for x in b['weekday_images'])==6080368
    assert 'NOT peak RAM' in b['limitation']


def test_offline_compiler_preserves_cropped_weekday_pixels():
    from tools.creek_bin import decode_image,parse
    candidate=ROOT/'offline-ewrcompass_24d08@LC.bin'
    if not candidate.exists():pytest.skip('Private offline compiler output absent')
    data=candidate.read_bytes();report=image_budget(data)
    assert sum(x['decoded_pixel_bytes'] for x in report['weekday_images'])==56364
    assert report['decoded_image_bytes_sum']==3325440
    expected=revision8_images(ROOT/'source')
    for i in range(7):
        name=f'WWeek_{i}_8888.png'
        assert decode_image(data,name).tobytes()==expected[f'WWeek/{name}'].tobytes()
    assert parse(data)['name']=='ewrcompass_24d08@LC'
