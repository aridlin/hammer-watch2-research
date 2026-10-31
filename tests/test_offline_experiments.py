import copy,json
from pathlib import Path
import pytest
from tools.offline_experiments import control_model,NAMES
from tools.adventurer_digital import TARGET
from tools.creek_bin import parse
ROOT=Path('faces/local/adventurer')


def test_controls_are_explicit_and_do_not_mutate_the_source():
    model={'name':TARGET,'platform':'ats3089C','resolution_ratio':'466x466','item':[],'fade_item':[]}
    saved=copy.deepcopy(model)
    renamed=control_model(model,'renamed_factory')
    assert renamed=={**model,'name':NAMES['renamed_factory']} and model==saved
    seconds=control_model(model,'factory_plus_seconds')
    assert seconds['item'][0]['widget']=='text' and seconds['item'][0]['type']=='second'
    assert seconds['fade_item']==model['fade_item']
    with pytest.raises(ValueError):control_model(model,'unknown')
    with pytest.raises(ValueError):control_model(model,'cropped_original_compass')


def test_compiled_factory_control_preserves_all_original_non_layout_resources():
    original=ROOT/'official-green.bin';clone=ROOT/'offline-controls-v1'/f"{NAMES['renamed_factory']}.bin"
    if not original.exists() or not clone.exists():pytest.skip('Private real compile samples absent')
    a=parse(original.read_bytes());b=parse(clone.read_bytes())
    assets=lambda r:[(x['name'],x['sha256']) for x in r['resources'] if x['name']!='dial.json']
    assert assets(a)==assets(b)
    first=next(x['json'] for x in a['resources'] if x['name']=='dial.json')
    second=next(x['json'] for x in b['resources'] if x['name']=='dial.json')
    assert second==control_model(first,'renamed_factory')


def test_compiled_seconds_control_changes_only_one_widget_and_name():
    original=ROOT/'official-green.bin';candidate=ROOT/'offline-controls-v1'/f"{NAMES['factory_plus_seconds']}.bin"
    if not original.exists() or not candidate.exists():pytest.skip('Private real compile samples absent')
    a=parse(original.read_bytes());b=parse(candidate.read_bytes())
    assert [(x['name'],x['sha256']) for x in a['resources'] if x['name']!='dial.json']==[(x['name'],x['sha256']) for x in b['resources'] if x['name']!='dial.json']
    first=next(x['json'] for x in a['resources'] if x['name']=='dial.json')
    second=next(x['json'] for x in b['resources'] if x['name']=='dial.json')
    assert second==control_model(first,'factory_plus_seconds')


def test_compiled_cropped_control_removes_only_two_weather_sensor_widgets():
    base=ROOT/'offline-ewrcompass_24d08@LC.bin';candidate=ROOT/'offline-controls-v1'/f"{NAMES['cropped_original_compass']}.bin"
    if not base.exists() or not candidate.exists():pytest.skip('Private real compile samples absent')
    a=parse(base.read_bytes());b=parse(candidate.read_bytes())
    first=next(x['json'] for x in a['resources'] if x['name']=='dial.json')
    second=next(x['json'] for x in b['resources'] if x['name']=='dial.json')
    assert second==control_model(first,'cropped_original_compass')
    assert len(first['item'])-len(second['item'])==2
    assert [(x['name'],x['sha256']) for x in a['resources'] if x['name']!='dial.json']==[(x['name'],x['sha256']) for x in b['resources'] if x['name']!='dial.json']


def test_source_controls_refuse_public_or_external_output(tmp_path):
    from tools.offline_experiments import prepare_controls
    source=tmp_path/'synthetic-source';(source/'firmware').mkdir(parents=True)
    model={'name':TARGET,'platform':'ats3089C','resolution_ratio':'466x466','item':[],'fade_item':[]}
    (source/'firmware/dial.json').write_text(json.dumps(model))
    destination=tmp_path/'outside-private-face-tree'
    with pytest.raises(ValueError,match='ignored faces/local'):prepare_controls(source,destination)
    assert not destination.exists()
