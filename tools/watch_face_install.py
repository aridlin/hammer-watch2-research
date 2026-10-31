"""Prepare or explicitly execute one separately named ADVENTURER test-face upload.

Default is offline preparation. Execution requires --execute and an exact reviewed
SHA-256, current device inquiries, private logs, and an already-connected watch.
No firmware, binding, deletion or arbitrary-file API exists. An explicit
reviewed-test resume mode requires a verified nonzero receiver offset/CRC.
"""
import argparse
import binascii
import hashlib
import json
import os
from pathlib import Path
import struct
import time
from .adventurer_digital import TEST_NAME,TEST_NAMES,transform
from .bluez_watch_state import load_target
from .creek_bin import parse,read_binary,decode_image
from .creek_inquiry import ROOT,SERVICE,WRITE,NOTIFY,run as inquire

FILENAME=(TEST_NAME+'.bin').encode()
ORIGINAL_SHA='bcb39cc699ffc6289009ef5b23431b76bfa23bbffb6d099afe4c0da095fab84e'


# Suspended after physical reports of skipped seconds, slow compass and a reboot.
# No CLI override: resume only after an offline stability review and new approval.
LIVE_EXECUTION_SUSPENDED=True


class InstallationSuspended(RuntimeError):
    pass


def require_live_execution():
    if LIVE_EXECUTION_SUSPENDED:
        raise InstallationSuspended('Custom face installations suspended after reported watch reboot; offline analysis remains available')


def status_keys(revision):
    if revision==1:return 'standalone_test_entry_present','active_is_standalone_test'
    if revision==3:return 'revision3_test_entry_present','active_is_revision3_test'
    if revision==4:return 'revision4_test_entry_present','active_is_revision4_test'
    if revision==5:return 'revision5_test_entry_present','active_is_revision5_test'
    if revision==6:return 'revision6_test_entry_present','active_is_revision6_test'
    if revision==7:return 'revision7_test_entry_present','active_is_revision7_test'
    raise ValueError('Unsupported physical test revision')


def prepare(candidate,original,revision=1):
    status_keys(revision)
    if hashlib.sha256(original).hexdigest()!=ORIGINAL_SHA:raise ValueError('Unexpected original')
    source=parse(original);report=parse(candidate)
    model=next(r['json'] for r in report['resources'] if r['name']=='dial.json')
    original_model=next(r['json'] for r in source['resources'] if r['name']=='dial.json')
    expected,_=transform(original_model,standalone=True,revision=revision)
    if report['name']!=TEST_NAMES[revision] or model!=expected:raise ValueError('Only the reviewed standalone digital layout is accepted')
    from .adventurer_source import PATCH_PATHS,clean_meter_background,revision4_images,revision5_images,revision6_images,revision7_images
    changed=set(PATCH_PATHS) if revision==3 else set()
    expected_images={}
    if revision>=4:
        image_transform={4:revision4_images,5:revision5_images,6:revision6_images,7:revision7_images}[revision]
        expected_images={Path(k).name:v for k,v in image_transform(ROOT/'faces/local/adventurer/source').items()}
        for name in PATCH_PATHS:
            if revision>=5 and name=='bg_0888.bmp':continue
            expected_images[name]=clean_meter_background(decode_image(original,name),name)
            if name!='bg_0888.bmp':expected_images[name].paste((0,0,0),(211,287,255,329))
        changed=set(expected_images)
    old_resources={r['name']:r for r in source['resources'] if r['name']!='dial.json'}
    new_resources={r['name']:r for r in report['resources'] if r['name']!='dial.json'}
    if set(new_resources)!=set(old_resources)|set(expected_images):raise ValueError('Resource membership differs')
    preserved=0
    for name,new in new_resources.items():
        if name in changed:
            expected_image=expected_images[name] if revision>=4 else clean_meter_background(decode_image(original,name),name)
            actual_image=decode_image(candidate,name)
            if expected_image.convert('RGBA').tobytes()!=actual_image.convert('RGBA').tobytes():raise ValueError('Image change exceeds reviewed source transform')
        elif old_resources[name]['sha256']!=new['sha256']:raise ValueError('Non-layout resource differs')
        else:preserved+=1
    if len(candidate)>1024*1024:raise ValueError('Test face exceeds limit')
    return {'filename':TEST_NAMES[revision]+'.bin','revision':revision,'bytes':len(candidate),'sha256':report['sha256'],
            'container_crc_valid':report['crc_valid'],'preserved_non_layout_resources':preserved,'patched_meter_backgrounds':sorted(changed),
            'factory_filename_different':True,'palette':'original multi-palette selection',
            'physical_installation_attempted':False,'activation':'select test face manually on watch after upload'}


def frames(data,chunk=180,revision=1):
    status_keys(revision)
    filename=(TEST_NAMES[revision]+'.bin').encode()
    if not 20<=chunk<=180 or not 0<len(data)<=1024*1024:raise ValueError('Invalid bounded transfer')
    yield 'start',b'\xd1\0'+struct.pack('<II',len(data),len(data))+b'\x01'+filename+b'\0',0,0
    crc=0
    for offset in range(0,len(data),chunk):
        part=data[offset:offset+chunk];crc=binascii.crc_hqx(part,crc)
        yield 'data',b'\xd2\0'+part,offset+len(part),crc
    yield 'end',b'\xd4\0\0'+struct.pack('<I',crc),len(data),crc


def validate_ack(packet,opcode,stage,offset,crc):
    if len(packet) not in (3,7,11) or packet[0]!=opcode:raise ValueError('Unknown acknowledgment shape')
    if packet[2]!=0:raise ValueError('Watch rejected transfer; no retry attempted')
    if stage=='data':
        if len(packet)!=11 or struct.unpack_from('<I',packet,3)[0]!=offset or struct.unpack_from('<I',packet,7)[0]!=crc:
            raise ValueError('Offset/CRC mismatch; no resume attempted')


def verified_resume_offset(ack,data,chunk):
    validate_ack(ack,0xd3,'query-position',0,0)
    if len(ack)!=11:raise ValueError('Resume query requires offset and CRC')
    offset,remote_crc=struct.unpack_from('<II',ack,3)
    if not 0<offset<=len(data) or (offset%chunk and offset!=len(data)) or binascii.crc_hqx(data[:offset],0)!=remote_crc:
        raise ValueError('Nonzero aligned receiver offset/CRC does not match reviewed test')
    return offset,remote_crc


def check_metadata(device,dial,mtu,size,resume=False,revision=1):
    present_key,_=status_keys(revision)
    for result in [device,dial,mtu]:
        if result.get('response_code')!=0 or not result.get('crc16_valid'):raise ValueError('Fresh metadata inquiry failed')
    d=device['present_numeric_fields'];f=dial['present_numeric_fields'];m=mtu['present_numeric_fields']
    if (d.get('device_id'),d.get('firmware_major'),d.get('firmware_minor',0),d.get('firmware_patch'),d.get('platform_enum'),d.get('device_color'))!=(2039,2,0,12,3,72):
        raise ValueError('Physical device metadata differs from reviewed target')
    if f.get('framework_version')!=8 or f.get('compression')!=4:raise ValueError('Framework/compression mismatch')
    if resume:
        if not dial.get(present_key) or not dial.get('adventurer_entry_present'):
            raise ValueError('Expected partial test and intact factory entry for resume')
    elif dial.get(present_key):raise ValueError('Test face already exists; overwrites are disabled')
    if dial['face_entry_count']>=f.get('all_face_limit',0):raise ValueError('No free face slot')
    if f.get('total_bytes',0)-f.get('cloud_used_bytes',0)-f.get('photo_used_bytes',0)<size:raise ValueError('Insufficient reported storage')
    if m.get('transfer_mtu',0)<40:raise ValueError('Transfer MTU too small')


def execute(data,target,destination,resume=False,revision=1):
    require_live_execution()
    present_key,active_key=status_keys(revision)
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    if not destination.resolve().is_relative_to(ROOT/'private'):raise ValueError('Execution logs must remain private')
    destination.mkdir(parents=True,exist_ok=False)
    address=load_target(target)
    results={op:inquire(op,target,destination/(op+'.jsonl')) for op in ['device-info','dial-info','mtu-info']}
    check_metadata(results['device-info'],results['dial-info'],results['mtu-info'],len(data),resume,revision)
    DBusGMainLoop(set_as_default=True);bus=dbus.SystemBus()
    objects=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager').GetManagedObjects()
    targets=[str(p) for p,v in objects.items() if str(v.get('org.bluez.Device1',{}).get('Address','')).upper()==address]
    if len(targets)!=1:raise ValueError('Target ambiguous')
    services={str(p) for p,v in objects.items() if str(v.get('org.bluez.GattService1',{}).get('Device',''))==targets[0] and str(v['org.bluez.GattService1'].get('UUID','')).lower()==SERVICE}
    chars={str(v['org.bluez.GattCharacteristic1']['UUID']).lower():(str(p),v['org.bluez.GattCharacteristic1']) for p,v in objects.items() if str(v.get('org.bluez.GattCharacteristic1',{}).get('Service','')) in services}
    if WRITE not in chars or NOTIFY not in chars:raise ValueError('Physical Creek service missing')
    att_mtu=int(chars[WRITE][1].get('MTU',0))
    if att_mtu<43:raise ValueError('Negotiated ATT MTU is too small; no file writes attempted')
    write=dbus.Interface(bus.get_object('org.bluez',chars[WRITE][0]),'org.bluez.GattCharacteristic1')
    notify=dbus.Interface(bus.get_object('org.bluez',chars[NOTIFY][0]),'org.bluez.GattCharacteristic1')
    queue=[];loop=GLib.MainLoop();expected_opcode=None;last_ack=None
    with os.fdopen(os.open(destination/'upload.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as log:
        def record(event,**fields):log.write(json.dumps({'event':event,**fields})+'\n');log.flush()
        def changed(interface,values,invalidated):
            if str(interface)!='org.bluez.GattCharacteristic1' or 'Value' not in values:return
            packet=bytes(values['Value'])
            if not packet or packet[0] not in (0xd1,0xd2,0xd3,0xd4):return
            if packet==last_ack:
                record('duplicate_ack_ignored',opcode=packet[0]);return
            if packet[0]!=expected_opcode:
                record('other_opcode_ack_ignored',opcode=packet[0]);return
            if len(packet)>11 or len(queue)>8:record('unexpected_ack');loop.quit();return
            queue.append(packet);loop.quit()
        receiver=bus.add_signal_receiver(changed,dbus_interface='org.freedesktop.DBus.Properties',signal_name='PropertiesChanged',path=chars[NOTIFY][0])
        started=False;completed=False
        try:
            notify.StartNotify(timeout=10);started=True
            chunk=min(180,att_mtu-5);count=0
            def transact(stage,packet,offset,crc):
                nonlocal expected_opcode,last_ack
                if len(packet)>att_mtu-3:raise ValueError('Frame exceeds negotiated MTU')
                expected_opcode=packet[0];queue.clear();record('send',stage=stage,bytes=len(packet),offset=offset)
                write.WriteValue(dbus.Array(packet,signature='y'),dbus.Dictionary({'type':'command'},signature='sv'),timeout=10)
                if not queue:
                    timer=[None]
                    def timeout():timer[0]=None;loop.quit();return False
                    timer[0]=GLib.timeout_add_seconds(8,timeout);loop.run()
                    if timer[0]:GLib.source_remove(timer[0])
                if len(queue)!=1:raise ValueError('ACK missing/ambiguous; upload stopped without retry')
                ack=queue.pop(0);record('ack',hex=ack.hex());last_ack=ack
                validate_ack(ack,packet[0],stage,offset,crc)
                return ack
            resume_offset=0
            if resume:
                ack=transact('query-position',b'\xd3\0',0,0)
                resume_offset,remote_crc=verified_resume_offset(ack,data,chunk)
                record('verified_resume',offset=resume_offset,crc=remote_crc)
            for stage,packet,offset,crc in frames(data,chunk,revision):
                if resume and (stage=='start' or (stage=='data' and offset<=resume_offset)):continue
                transact(stage,packet,offset,crc);count+=1
                if count%100==0:print(json.dumps({'uploaded_bytes_acknowledged':offset,'total_bytes':len(data)}),flush=True)
            completed=True;record('transfer_acknowledged',bytes=len(data))
        finally:
            if started:
                try:notify.StopNotify(timeout=5)
                except dbus.DBusException:pass
            receiver.remove()
    if completed:
        time.sleep(1)
        final=inquire('dial-info',target,destination/'dial-after.jsonl')
        return {'transfer_acknowledged':True,'revision':revision,'filename':TEST_NAMES[revision]+'.bin','test_entry_confirmed':final.get(present_key,False),
                'test_face_active':final.get(active_key,False),'factory_entry_present':final.get('adventurer_entry_present',False),
                'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'resumed_from_verified_offset':resume_offset,'automatic_activation_command_sent':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision',type=int,choices=[1,3,4,5,6,7],default=1)
    p.add_argument('--candidate',required=True,type=Path)
    p.add_argument('--original',type=Path,default=Path('faces/local/adventurer/official-green.bin'))
    p.add_argument('--resume-reviewed-test',action='store_true',help='Only continue an already-approved partial test after verifying receiver prefix CRC; no new D1')
    p.add_argument('--execute',action='store_true');p.add_argument('--confirm-sha256')
    p.add_argument('--target',type=Path);p.add_argument('--destination',type=Path)
    a=p.parse_args()
    try:
        if a.execute:require_live_execution()
        data=read_binary(a.candidate);plan=prepare(data,read_binary(a.original),a.revision)
        if not a.execute:print(json.dumps(plan,indent=2));return 0
        if a.confirm_sha256!=plan['sha256'] or a.target is None or a.destination is None:
            raise ValueError('Execution requires reviewed hash, private target and new log destination')
        print(json.dumps(execute(data,a.target,a.destination,resume=a.resume_reviewed_test,revision=a.revision),indent=2));return 0
    except InstallationSuspended as exc:
        print(json.dumps({'error_type':'InstallationSuspended','reason':str(exc),'no_device_access':True}));return 2
    except Exception as exc:
        print(json.dumps({'error_type':type(exc).__name__,'details_omitted':True,'no_automatic_retry':True}));return 2


if __name__=='__main__':raise SystemExit(main())
