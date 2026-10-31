"""Real source/compiler validation; skipped when private samples are unavailable."""
import json
from pathlib import Path
import pytest
from tools.adventurer_digital import transform,CLOCK_TYPES,METER_TYPES
from tools.adventurer_source import revision4_images
from tools.watch_face_install import prepare

ROOT=Path('faces/local/adventurer')

def test_revision4_uses_factory_pointer_geometry_behind_clock():
    source=ROOT/'source/firmware/dial.json'
    if not source.exists():pytest.skip('Private source absent')
    original=json.loads(source.read_text());edited,_=transform(original,standalone=True,revision=4)
    for layer in ('item','fade_item'):
        pointers=lambda m:[x for x in m[layer] if x.get('widget')=='pointer' and x.get('type') in CLOCK_TYPES]
        assert pointers(edited)==pointers(original)
        assert not any(x.get('type')=='heart' or x.get('type') in METER_TYPES for x in edited[layer])
        clock=next(i for i,x in enumerate(edited[layer]) if x.get('type')=='time')
        assert all(i<clock for i,x in enumerate(edited[layer]) if x.get('widget')=='pointer')
        assert any(x.get('type')=='day' for x in edited[layer])
        assert any(x.get('type')=='month' and x.get('count')==12 for x in edited[layer])
        assert [x for x in edited[layer] if x.get('widget')=='compass']==[x for x in original[layer] if x.get('widget')=='compass']
    images=revision4_images(ROOT/'source')
    for i in (0,1):
        im=images[f'second/second_{i}_8888.png'];assert im.getbbox()==(16,8,18,20)
    assert len([n for n in images if n.startswith('Month/')])==12

def test_revision4_compiled_binary_passes_scoped_install_guard():
    candidate=ROOT/'ewr24dig04.bin'
    if not candidate.exists():pytest.skip('Private compiled face absent')
    report=prepare(candidate.read_bytes(),(ROOT/'official-green.bin').read_bytes(),revision=4)
    assert report['container_crc_valid'] and report['filename']=='ewr24dig04.bin'
