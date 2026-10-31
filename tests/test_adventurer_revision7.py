import json
from pathlib import Path
import pytest
from tools.adventurer_digital import transform,TEST_NAMES
from tools.adventurer_source import revision6_images,revision7_images
from tools.watch_face_install import prepare,frames
ROOT=Path('faces/local/adventurer')

def test_revision7_subtle_size_change_lower_weekday_and_preserved_bindings():
    p=ROOT/'source/firmware/dial.json'
    if not p.exists():pytest.skip('Private source absent')
    source=json.loads(p.read_text());before,_=transform(source,standalone=True,revision=6);after,_=transform(source,standalone=True,revision=7)
    assert after['name'].startswith('ewrcompass_') and after['name'].endswith('@LC') and after['name']!=source['name']
    for layer in ('item','fade_item'):
        sensors=lambda m:[x for x in m[layer] if x.get('widget') in {'compass','pointer'} or x.get('type') in {'angle','compass_icon'}]
        assert sensors(before)==sensors(after)
    clock=next(x for x in after['item'] if x.get('type')=='time');second=next(x for x in after['item'] if x.get('widget')=='text' and x.get('type')=='second')
    assert (clock['x']+second['x']+second['w'])/2==233
    a=revision6_images(ROOT/'source');b=revision7_images(ROOT/'source')
    expected={*(f'Time/Time_{i}_8888.png' for i in range(11)),*(f'WWeek/WWeek_{i}_8888.png' for i in range(7))}
    assert {n for n in a if a[n].tobytes()!=b[n].tobytes()}==expected
    for i in range(10):assert b[f'Time/Time_{i}_8888.png'].size==(47,57)
    assert b['Time/Time_10_8888.png'].size==(20,57)
    for i in range(7):
        old=a[f'WWeek/WWeek_{i}_8888.png'].getbbox();new=b[f'WWeek/WWeek_{i}_8888.png'].getbbox()
        assert 6<=new[3]-old[3]<=10
    start=next(frames(b'abc',revision=7))[1]
    assert TEST_NAMES[7].encode()+b'.bin\0' in start


def test_revision7_compiled_guard():
    p=ROOT/(TEST_NAMES[7]+'.bin')
    if not p.exists():pytest.skip('Private compiled candidate absent')
    assert prepare(p.read_bytes(),(ROOT/'official-green.bin').read_bytes(),7)['container_crc_valid']
