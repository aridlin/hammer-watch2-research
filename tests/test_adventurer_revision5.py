import json
from pathlib import Path
import pytest
from tools.adventurer_digital import transform
from tools.adventurer_source import revision5_images
from tools.watch_face_install import prepare
from tools.creek_bin import decode_image
ROOT=Path('faces/local/adventurer')

def test_weather_font_date_and_sensor_widgets():
    p=ROOT/'source/firmware/dial.json'
    if not p.exists() or not (ROOT/'comparison-weather.bin').exists():pytest.skip('Private sources absent')
    edited,_=transform(json.loads(p.read_text()),standalone=True,revision=5)
    assert any(x.get('type')=='compass_icon' for x in edited['item'])
    assert any(x.get('type')=='angle' and x.get('widget')=='text' for x in edited['item'])
    assert not any(x.get('type')=='heart' for x in edited['item'])
    assert any(x.get('type')=='day' and x.get('widget')=='curved' for x in edited['item'])
    images=revision5_images(ROOT/'source');weather=(ROOT/'comparison-weather.bin').read_bytes()
    for i in range(11):
        assert images[f'Time/Time_{i}_8888.png'].tobytes()==decode_image(weather,f'Time_{i}_8888.png').tobytes()
    for i in range(7):
        im=images[f'WWeek/WWeek_{i}_8888.png'];assert im.size==(466,466)
        assert im.getbbox() is not None
        assert all(pixel[:3]==(246,127,49) for pixel in im.get_flattened_data() if pixel[3])
    original=decode_image((ROOT/'official-green.bin').read_bytes(),'bg_0888.bmp')
    cleaned=images['bg_0888.bmp']
    assert original.getpixel((233,331))!=cleaned.getpixel((233,331))


def test_revision5_compiled_guard():
    p=ROOT/'ewr24dig05.bin'
    if not p.exists():pytest.skip('Private compiled candidate absent')
    assert prepare(p.read_bytes(),(ROOT/'official-green.bin').read_bytes(),5)['container_crc_valid']
