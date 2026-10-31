import binascii,json,struct
from pathlib import Path
import pytest
from tools.watch_face_install import prepare,frames,validate_ack,check_metadata,FILENAME
from tools.creek_transfer import reconstruct_events


def test_full_codec_and_ack_checks_without_radio(tmp_path):
    data=bytes(range(256))*3
    items=list(frames(data))
    assert b'ewrcompass_0819@LC.bin' not in items[0][1]
    assert FILENAME+b'\0'==items[0][1][11:]
    for stage,packet,offset,crc in items:
        ack=bytes([packet[0],0,0])+struct.pack('<II',offset,crc)
        validate_ack(ack,packet[0],stage,offset,crc)
        if stage=='data':
            bad=ack[:-1]+bytes([ack[-1]^1])
            with pytest.raises(ValueError):validate_ack(bad,packet[0],stage,offset,crc)
    path=tmp_path/'trace.jsonl';path.write_text(''.join(json.dumps({'event':'gatt_write','hex':packet.hex()})+'\n' for _,packet,_,_ in items))
    reconstructed,_=reconstruct_events(path)
    assert reconstructed[0][0]==data
    assert max(len(packet) for _,packet,_,_ in items)<=182
    with pytest.raises(ValueError):validate_ack(b'\xd1\0\x01',0xd1,'start',0,0)


def metadata():
    return ({'response_code':0,'crc16_valid':True,'present_numeric_fields':{'device_id':2039,'firmware_major':2,'firmware_patch':12,'platform_enum':3,'device_color':72}},
            {'response_code':0,'crc16_valid':True,'face_entry_count':10,'standalone_test_entry_present':False,'present_numeric_fields':{'framework_version':8,'compression':4,'all_face_limit':24,'total_bytes':41943040,'cloud_used_bytes':2719744}},
            {'response_code':0,'crc16_valid':True,'present_numeric_fields':{'transfer_mtu':244}})


def test_preflight_refuses_existing_face_wrong_device_and_full_storage():
    d,f,m=metadata();check_metadata(d,f,m,429383)
    f['standalone_test_entry_present']=True
    with pytest.raises(ValueError):check_metadata(d,f,m,429383)
    d,f,m=metadata();d['present_numeric_fields']['device_id']=1
    with pytest.raises(ValueError):check_metadata(d,f,m,429383)
    d,f,m=metadata();f['face_entry_count']=24
    with pytest.raises(ValueError):check_metadata(d,f,m,429383)
    d,f,m=metadata();f['present_numeric_fields']['total_bytes']=1
    with pytest.raises(ValueError):check_metadata(d,f,m,429383)


def test_vendor_compiled_standalone_and_prepare_when_available():
    root=Path('faces/local/adventurer');p=root/'ewr24digital.bin'
    if not p.exists():pytest.skip('Private SDK-compiled standalone candidate absent')
    original=(root/'official-green.bin').read_bytes();data=p.read_bytes()
    result=prepare(data,original)
    assert result['filename']=='ewr24digital.bin' and result['factory_filename_different']
    assert result['preserved_non_layout_resources']==127
    assert not result['physical_installation_attempted']
    with pytest.raises(ValueError):prepare(original,original)
    with pytest.raises(ValueError):prepare(data,original[:-1])


def test_resume_requires_matching_nonzero_prefix_and_intact_factory_entry():
    from tools.watch_face_install import verified_resume_offset
    data=bytes(range(256))*2
    def ack(offset,crc):return b'\xd3\0\0'+struct.pack('<II',offset,crc)
    crc=binascii.crc_hqx(data[:180],0)
    assert verified_resume_offset(ack(180,crc),data,180)==(180,crc)
    for packet in [ack(0,0),ack(181,binascii.crc_hqx(data[:181],0)),ack(180,crc^1),ack(999,0)]:
        with pytest.raises(ValueError):verified_resume_offset(packet,data,180)
    d,f,m=metadata();f['standalone_test_entry_present']=True
    with pytest.raises(ValueError):check_metadata(d,f,m,len(data),resume=True)
    f['adventurer_entry_present']=True;check_metadata(d,f,m,len(data),resume=True)


@pytest.mark.parametrize('resume',[False,True])
@pytest.mark.parametrize('revision',[1,3])
def test_dbus_sender_full_flow_query_and_duplicate_notifications(tmp_path,monkeypatch,resume,revision):
    import sys,types
    import tools.watch_face_install as install
    from tools.creek_inquiry import SERVICE,WRITE,NOTIFY
    monkeypatch.setattr(install,'LIVE_EXECUTION_SUSPENDED',False) # Explicit simulated D-Bus only.
    address='01:02:03:04:05:06';device='/lab/device';service=device+'/service';wp=service+'/write';np=service+'/notify'
    data=bytes(range(256))*3;received=bytearray(data[:180] if resume else b'');sent=[]
    state={'callback':None,'last_ack':None,'dial_reads':0}
    class Loop:
        def quit(self):pass
        def run(self):raise AssertionError('Expected synchronous fake ACK was dropped')
    class Radio:
        def StartNotify(self,**kwargs):pass
        def StopNotify(self,**kwargs):pass
        def WriteValue(self,value,options,**kwargs):
            value=bytes(value);sent.append(value);op=value[0]
            if op==0xd1:received.clear();ack=b'\xd1\0\0'
            elif op==0xd3:ack=b'\xd3\0\0'+struct.pack('<II',len(received),binascii.crc_hqx(received,0))
            elif op==0xd2:
                received.extend(value[2:]);ack=b'\xd2\0\0'+struct.pack('<II',len(received),binascii.crc_hqx(received,0))
            elif op==0xd4:
                assert struct.unpack_from('<I',value,3)[0]==binascii.crc_hqx(received,0)
                ack=b'\xd4\0\0'
            else:raise AssertionError('Unexpected mutation command')
            callback=state['callback']
            if state['last_ack'] is not None:callback('org.bluez.GattCharacteristic1',{'Value':state['last_ack']},[])
            callback('org.bluez.GattCharacteristic1',{'Value':ack},[]);state['last_ack']=ack
    radio=Radio()
    objects={device:{'org.bluez.Device1':{'Address':address}},
             service:{'org.bluez.GattService1':{'Device':device,'UUID':SERVICE}},
             wp:{'org.bluez.GattCharacteristic1':{'Service':service,'UUID':WRITE,'MTU':247}},
             np:{'org.bluez.GattCharacteristic1':{'Service':service,'UUID':NOTIFY}}}
    class Bus:
        def get_object(self,name,path):return self if path=='/' else radio
        def GetManagedObjects(self):return objects
        def add_signal_receiver(self,callback,**kwargs):
            state['callback']=callback;return types.SimpleNamespace(remove=lambda:None)
    bus=Bus();dbus=types.ModuleType('dbus');dbus.SystemBus=lambda:bus;dbus.Interface=lambda obj,interface:obj
    dbus.Array=lambda data,signature:bytes(data);dbus.Dictionary=lambda data,signature:data;dbus.DBusException=Exception
    glib=types.ModuleType('dbus.mainloop.glib');glib.DBusGMainLoop=lambda **kwargs:None
    repository=types.ModuleType('gi.repository');repository.GLib=types.SimpleNamespace(MainLoop=Loop,timeout_add_seconds=lambda *args:1,source_remove=lambda *args:None)
    for key,module in [('dbus',dbus),('dbus.mainloop',types.ModuleType('dbus.mainloop')),('dbus.mainloop.glib',glib),('gi',types.ModuleType('gi')),('gi.repository',repository)]:monkeypatch.setitem(sys.modules,key,module)
    def inquiry(operation,target,path):
        d,f,m=metadata();f['adventurer_entry_present']=True
        if operation=='dial-info':
            state['dial_reads']+=1;f['standalone_test_entry_present']=resume or state['dial_reads']>1;f['revision3_test_entry_present']=resume or state['dial_reads']>1
            return f
        return d if operation=='device-info' else m
    monkeypatch.setattr(install,'inquire',inquiry);monkeypatch.setattr(install,'ROOT',tmp_path);monkeypatch.setattr(install.time,'sleep',lambda _:None)
    target=tmp_path/'target.json';target.write_text(json.dumps({'address':address}));target.chmod(0o600)
    result=install.execute(data,target,tmp_path/'private/output',resume=resume,revision=revision)
    assert received==data and result['transfer_acknowledged'] and result['test_entry_confirmed']
    assert result['factory_entry_present'] and not result['automatic_activation_command_sent']
    assert sent[0][0]==(0xd3 if resume else 0xd1)
    assert sum(packet[0]==0xd1 for packet in sent)==(0 if resume else 1)


def test_actual_watch_acknowledgments_when_available():
    root=Path('private/emulator/physical-test-upload-03');candidate=Path('faces/local/adventurer/ewr24digital.bin')
    if not (root/'upload.jsonl').exists() or not candidate.exists():pytest.skip('Private physical upload capture absent')
    data=candidate.read_bytes();expected={offset:crc for stage,packet,offset,crc in frames(data) if stage=='data'}
    stage=None;offset=0;checked=0;complete=False
    for line in (root/'upload.jsonl').read_text().splitlines():
        event=json.loads(line)
        if event['event']=='send':stage=event['stage'];offset=event['offset']
        elif event['event']=='ack':
            ack=bytes.fromhex(event['hex'])
            if stage=='query-position':
                from tools.watch_face_install import verified_resume_offset
                assert verified_resume_offset(ack,data,180)[0]==180
            else:
                opcode=0xd2 if stage=='data' else 0xd4
                crc=expected[offset] if stage=='data' else binascii.crc_hqx(data,0)
                validate_ack(ack,opcode,stage,offset,crc)
            checked+=1
        elif event['event']=='transfer_acknowledged':complete=True
    assert checked==2387 and complete


def test_revision3_preparation_allows_only_reviewed_meter_removal():
    root=Path('faces/local/adventurer');candidate=root/'ewr24dig03.bin'
    if not candidate.exists():pytest.skip('Private revision3 compiler output absent')
    data=candidate.read_bytes();original=(root/'official-green.bin').read_bytes()
    plan=prepare(data,original,revision=3)
    assert plan['filename']=='ewr24dig03.bin'
    assert plan['preserved_non_layout_resources']==124
    assert len(plan['patched_meter_backgrounds'])==3
    with pytest.raises(ValueError):prepare(data,original,revision=1)


def test_reboot_quarantine_blocks_before_radio_or_files(tmp_path,monkeypatch):
    import tools.watch_face_install as install
    assert install.LIVE_EXECUTION_SUSPENDED
    monkeypatch.setattr(install,'load_target',lambda _:pytest.fail('Target must not be read'))
    monkeypatch.setattr(install,'inquire',lambda *a,**k:pytest.fail('Radio must not be used'))
    destination=tmp_path/'must-not-exist'
    with pytest.raises(install.InstallationSuspended):
        install.execute(b'not-read',tmp_path/'absent',destination,revision=7)
    assert not destination.exists()
