import copy
import json
from pathlib import Path
import pytest
from tools.adventurer_digital import TARGET,transform,build,format_hhmm


def synthetic_model():
    return {'name':TARGET,'platform':'ats3089C','resolution_ratio':'466x466',
            'unknown_extension':{'retain':True},'cur_sn':0,
            'item':[{'widget':'pointer','type':t} for t in ['hour','min','second']]+[
                {'widget':'compass','type':'angle','unknown':23},
                {'widget':'text','type':'air_pressure','font':'Data'},
                {'widget':'icon','type':'compass_hint','y':144},
                {'widget':'icon','type':'other','sn_color_list':['#B0CD53','#F67F31'],'color':'0'},
                {'widget':'icon','type':'other','picture':'Dot_8888.png'}],
            'fade_item':[{'widget':'pointer','type':t} for t in ['hour','min']]}


def test_clock_replacement_preserves_unknowns_and_sensor_bindings():
    original=synthetic_model();snapshot=copy.deepcopy(original)
    edited,report=transform(original)
    assert original==snapshot
    assert edited['unknown_extension']==original['unknown_extension']
    assert edited['item'][0]==original['item'][3]
    assert edited['item'][1]==original['item'][4]
    assert not any(x.get('widget')=='pointer' for x in edited['item'])
    assert edited['item'][-1]['type']=='time'
    assert edited['fade_item'][-1]['type']=='time'
    assert report['removed_clock_items']=={'item':4,'fade_item':2}
    assert report['palette_index'] is None


def test_orange_palette_explicit_and_source_validation():
    edited,_=transform(synthetic_model(),1)
    assert edited['cur_sn']==1
    assert next(x for x in edited['item'] if 'sn_color_list' in x)['color']=='#F67F31'
    for field,value in [('name','wrong'),('platform','ats3085c')]:
        m=synthetic_model();m[field]=value
        with pytest.raises(ValueError):transform(m)
    with pytest.raises(ValueError):transform(synthetic_model(),2)


@pytest.mark.parametrize('hour,minute,text',[(0,0,'00:00'),(9,5,'09:05'),(12,0,'12:00'),(23,59,'23:59')])
def test_preview_time_boundaries(hour,minute,text):
    assert format_hhmm(hour,minute)==text


@pytest.mark.parametrize('hour,minute',[(24,0),(-1,0),(0,60),(True,0)])
def test_invalid_times(hour,minute):
    with pytest.raises(ValueError):format_hhmm(hour,minute)


def test_real_adventurer_candidate_and_lossless_original_when_available():
    path=Path('faces/local/adventurer/official-green.bin')
    if not path.exists():pytest.skip('Private real sample not supplied')
    from tools.creek_bin import parse,export_ir,rebuild
    data=path.read_bytes();assert rebuild(export_ir(data))==data
    result,model,report=build(data,1)
    assert report['crc_valid'] and report['unchanged_asset_count']==127
    assert not report['installation_tested']
    assert model['platform']=='ats3089C'
    assert parse(result)['resources'][0]['json']==model


def test_vendor_outputs_match_official_original_and_candidate_layout_when_available():
    root=Path('faces/local/adventurer')
    paths=[root/n for n in ['official-green.bin','vendor-oracle-original.bin','vendor-digital-orange.bin']]
    if not all(p.exists() for p in paths):pytest.skip('Private emulator compiler outputs not supplied')
    from tools.creek_bin import parse
    assert paths[0].read_bytes()==paths[1].read_bytes()
    expected,model,_=build(paths[0].read_bytes(),1)
    actual=parse(paths[2].read_bytes());rebuilt=parse(expected)
    assert actual['resources'][0]['json']==model
    assert [(e['name'],e['sha256']) for e in actual['resources'][1:]]==[(e['name'],e['sha256']) for e in rebuilt['resources'][1:]]


def test_standalone_preserves_palette_and_renames_header_when_available():
    model=synthetic_model();edited,_=transform(model,standalone=True)
    assert edited['name']=='ewr24digital' and edited['cur_sn']==model['cur_sn']
    assert next(x for x in edited['item'] if 'sn_color_list' in x)['color']=='0'
    path=Path('faces/local/adventurer/official-green.bin')
    if not path.exists():pytest.skip('Private original absent')
    from tools.creek_bin import parse
    data,edited,report=build(path.read_bytes(),standalone=True)
    assert parse(data)['name']==edited['name']=='ewr24digital'
    assert report['crc_valid'] and report['unchanged_asset_count']==127
