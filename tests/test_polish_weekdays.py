from pathlib import Path
import pytest
from tools.adventurer_source import POLISH_WEEKDAYS,revision5_images,revision6_images
from tools.watch_face_install import prepare
ROOT=Path('faces/local/adventurer')

def test_polish_weekday_order_and_only_weekday_images_change():
    assert POLISH_WEEKDAYS==('pon','wt','śr','czw','pt','sob','ndz')
    if not (ROOT/'comparison-weather.bin').exists():pytest.skip('Private source absent')
    before=revision5_images(ROOT/'source');after=revision6_images(ROOT/'source')
    changed={name for name in before if before[name].tobytes()!=after[name].tobytes()}
    assert changed=={f'WWeek/WWeek_{i}_8888.png' for i in range(7)}
    for name in changed:assert after[name].getbbox() is not None

def test_polish_candidate_guard():
    candidate=ROOT/'ewr24dig06.bin'
    if not candidate.exists():pytest.skip('Private compiled candidate absent')
    assert prepare(candidate.read_bytes(),(ROOT/'official-green.bin').read_bytes(),6)['container_crc_valid']
