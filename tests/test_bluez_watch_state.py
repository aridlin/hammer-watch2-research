import json
import pytest
from tools.bluez_watch_state import load_target,summarize


def test_target_and_gatt_summary_omits_identifiers_values_and_other_devices(tmp_path):
    address='01:02:03:04:05:06';path='/dev/private_watch';other='/dev/unrelated'
    objects={path:{'org.bluez.Device1':{'Address':address,'Name':'private name','Paired':True,'UUIDs':['abcd']}},
             path+'/service':{'org.bluez.GattService1':{'Device':path,'UUID':'service'}},
             path+'/char':{'org.bluez.GattCharacteristic1':{'Service':path+'/service','UUID':'char','Flags':['notify','write'],'Value':b'secret'}},
             other:{'org.bluez.Device1':{'Address':'AA:BB:CC:DD:EE:FF','Name':'unrelated'}},
             other+'/service':{'org.bluez.GattService1':{'Device':other,'UUID':'unrelated-uuid'}}}
    result=summarize(objects,address)
    assert result['state']['Paired']
    assert result['gatt_services']==[{'uuid':'service','characteristics':[{'uuid':'char','flags':['notify','write']}]}]
    text=json.dumps(result)
    for private in [address,path,'secret','unrelated','private name']:assert private not in text
    target=tmp_path/'target.json';target.write_text(json.dumps({'address':address}));target.chmod(0o600)
    assert load_target(target)==address
    target.chmod(0o644)
    with pytest.raises(ValueError):load_target(target)


def test_absent_and_ambiguous_target():
    assert not summarize({},'01:02:03:04:05:06')['present_in_bluez_cache']
    interfaces={'org.bluez.Device1':{'Address':'01:02:03:04:05:06'}}
    with pytest.raises(ValueError):summarize({'/a':interfaces,'/b':interfaces},'01:02:03:04:05:06')
