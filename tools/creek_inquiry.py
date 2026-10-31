"""Bounded read-only Creek inquiries: exact recovered device/dial requests only.

No binding, set/delete, upload, arbitrary payload or firmware operation exists.
Physical execution uses system Python with dbus and GLib, on an already-connected
private target. Notification payloads stay in a new 0600 private JSONL file.
"""
import argparse
import binascii
import json
import os
from pathlib import Path
from .bluez_watch_state import load_target
from .creek_frame import Header
from .virtual_watch_protocol import Reassembler,selected_varints

ROOT=Path(__file__).resolve().parents[1]
REQUESTS={'device-info':bytes.fromhex('c10a010100010b000000000000'),
          'dial-info':bytes.fromhex('c13c010100160d000000000800'),
          'mtu-info':bytes.fromhex('c11e010100220d000000000801')}
SERVICE='00000ff0-0000-1000-8000-00805f9b34fb'
WRITE='00000001-0000-1000-8000-00805f9b34fb'
NOTIFY='00000002-0000-1000-8000-00805f9b34fb'


def request_for(operation):
    if operation not in REQUESTS:raise ValueError('Only recovered read-only inquiries are allowed')
    return REQUESTS[operation]


def byte_fields(data,wanted):
    """Bounded protobuf bytes-field reader; never publishes arbitrary fields."""
    if len(data)>4096:raise ValueError('Protobuf exceeds bounds')
    pos=0;result={}
    def read():
        nonlocal pos
        value=0
        for shift in range(0,70,7):
            if pos>=len(data):raise ValueError('Truncated varint')
            b=data[pos];pos+=1;value|=(b&127)<<shift
            if b<128:
                if value>=2**64:raise ValueError('Overflow')
                return value
        raise ValueError('Overflow')
    while pos<len(data):
        tag=read();field,wire=tag>>3,tag&7
        if not field:raise ValueError('Invalid field')
        if wire==0:read()
        elif wire==2:
            size=read();end=pos+size
            if end>len(data):raise ValueError('Truncated bytes')
            if field in wanted:result.setdefault(field,[]).append(data[pos:end])
            pos=end
        elif wire==1:pos+=8
        elif wire==5:pos+=4
        else:raise ValueError('Unsupported wire type')
        if pos>len(data):raise ValueError('Truncated fixed field')
    return result


def summarize_response(operation,packet,verify_crc=True):
    req=Header.parse(request_for(operation));h=Header.parse(packet)
    if ((h.sequence&127)!=(req.sequence&127) or (h.command_byte_0,h.command_byte_1)!=(req.command_byte_0,req.command_byte_1)
            or h.declared_length+2!=len(packet)):
        raise ValueError('Not a matching complete inquiry response')
    crc_valid=binascii.crc_hqx(packet[:-2],0xffff).to_bytes(2,'little')==packet[-2:]
    if verify_crc and not crc_valid:raise ValueError('Inquiry response CRC16 mismatch')
    body=packet[11:h.declared_length]
    result={'operation':operation,'response_code':h.code,'sequence_response_bit':bool(h.sequence&128),
            'response_bytes':len(packet),'identifiers_omitted':True,'trailer_integrity':'CRC16_CCITT_FALSE_little_endian_observed','crc16_valid':crc_valid}
    if h.code:return result
    if operation=='device-info':
        fields={1:'device_id',2:'firmware_major',3:'firmware_minor',4:'firmware_patch',6:'platform_enum',7:'shape_enum',8:'device_type_enum',21:'device_color',27:'binding_support_enum',29:'platform_pspkey_enum'}
        values=selected_varints(body,set(fields));result['present_numeric_fields']={fields[k]:v for k,v in values.items()}
        nested=byte_fields(body,{19})
        if nested.get(19):result['display']={str(k):v for k,v in selected_varints(nested[19][0],{1,2,3}).items()}
    elif operation=='dial-info':
        fields={1:'operate',2:'formula_mode',3:'framework_version',4:'cloud_capacity_count',5:'cloud_used_count',6:'photo_capacity_count',7:'photo_used_count',8:'wallpaper_capacity_count',9:'wallpaper_used_count',11:'total_bytes',12:'cloud_used_bytes',13:'photo_used_bytes',15:'compression',16:'function_flags',17:'photo_image_limit',18:'all_face_limit',19:'video_length_limit'}
        values=selected_varints(body,set(fields));result['present_numeric_fields']={fields[k]:v for k,v in values.items()}
        nested=byte_fields(body,{10,14});result['face_entry_count']=len(nested.get(10,[]))
        # Only report the known vendor target, never personal photo-face names.
        target=b'ewrcompass_0819@LC'
        def canonical(name):
            name=name.rstrip(b'\0')
            return name[:-4] if name.endswith(b'.bin') else name
        result['active_is_acquired_adventurer']=canonical(nested.get(14,[b''])[0])==target
        result['revision3_test_entry_present']=any(any(canonical(n)==b'ewr24dig03' for n in byte_fields(e,{4}).get(4,[])) for e in nested.get(10,[]))
        result['active_is_revision3_test']=canonical(nested.get(14,[b''])[0])==b'ewr24dig03'
        result['revision4_test_entry_present']=any(any(canonical(n)==b'ewr24dig04' for n in byte_fields(e,{4}).get(4,[])) for e in nested.get(10,[]))
        result['active_is_revision4_test']=canonical(nested.get(14,[b''])[0])==b'ewr24dig04'
        result['standalone_test_entry_present']=any(any(canonical(n)==b'ewr24digital' for n in byte_fields(e,{4}).get(4,[])) for e in nested.get(10,[]))
        result['active_is_standalone_test']=canonical(nested.get(14,[b''])[0])==b'ewr24digital'
        result['adventurer_entry_present']=any(any(canonical(n)==target for n in byte_fields(e,{4}).get(4,[])) for e in nested.get(10,[]))
    else:
        fields={1:'operate',2:'transfer_mtu',3:'ble_pairing',4:'bt_pairing',5:'bt_connected',6:'spp_prn',7:'hid_pairing',8:'ble_prn'}
        values=selected_varints(body,set(fields));result['present_numeric_fields']={fields[k]:v for k,v in values.items()}
    return result


def run(operation,target,destination):
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    payload=request_for(operation);address=load_target(target)
    if not destination.resolve().is_relative_to(ROOT/'private'):
        raise ValueError('Raw inquiry output must stay private')
    destination.parent.mkdir(parents=True,exist_ok=True)
    DBusGMainLoop(set_as_default=True);bus=dbus.SystemBus()
    manager=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager');objects=manager.GetManagedObjects()
    targets=[(str(p),v['org.bluez.Device1']) for p,v in objects.items() if str(v.get('org.bluez.Device1',{}).get('Address','')).upper()==address]
    if len(targets)!=1:raise ValueError('Target absent or ambiguous')
    device,props=targets[0]
    if not all(props.get(k,False) for k in ['Connected','Paired']):raise ValueError('Target must already be paired/connected')
    services={str(p) for p,v in objects.items() if str(v.get('org.bluez.GattService1',{}).get('Device',''))==device and str(v['org.bluez.GattService1'].get('UUID','')).lower()==SERVICE}
    chars={str(v['org.bluez.GattCharacteristic1']['UUID']).lower():str(p) for p,v in objects.items() if str(v.get('org.bluez.GattCharacteristic1',{}).get('Service','')) in services}
    if WRITE not in chars or NOTIFY not in chars:raise ValueError('Expected actual physical Creek characteristics')
    notify=dbus.Interface(bus.get_object('org.bluez',chars[NOTIFY]),'org.bluez.GattCharacteristic1')
    write=dbus.Interface(bus.get_object('org.bluez',chars[WRITE]),'org.bluez.GattCharacteristic1')
    result=None;count=0;assembler=Reassembler();loop=GLib.MainLoop()
    with os.fdopen(os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as log:
        def record(data):log.write(json.dumps(data)+'\n');log.flush()
        def changed(interface,values,invalidated):
            nonlocal result,count
            if str(interface)!='org.bluez.GattCharacteristic1' or 'Value' not in values:return
            packet=bytes(values['Value']);count+=1
            if count>128 or not 2<=len(packet)<=514:loop.quit();return
            record({'event':'notification','hex':packet.hex()})
            try:
                complete=assembler.feed(packet)
                if complete is not None:result=summarize_response(operation,complete);loop.quit()
            except ValueError:record({'event':'not_matching_or_unassembled'})
        subscription=bus.add_signal_receiver(changed,dbus_interface='org.freedesktop.DBus.Properties',signal_name='PropertiesChanged',path=chars[NOTIFY])
        started=False;timer=None
        try:
            notify.StartNotify(timeout=10);started=True
            record({'event':'read_only_inquiry','operation':operation,'hex':payload.hex()})
            write.WriteValue(dbus.Array(payload,signature='y'),dbus.Dictionary({'type':'command'},signature='sv'),timeout=10)
            def timeout():
                nonlocal timer
                timer=None;loop.quit();return False
            timer=GLib.timeout_add_seconds(12,timeout);loop.run()
            record({'event':'completed','matching_response':result is not None,'notification_count':count})
        finally:
            if timer:GLib.source_remove(timer)
            if started:
                try:notify.StopNotify(timeout=5)
                except dbus.DBusException:pass
            subscription.remove()
    if result is not None:
        result['bluez_services_resolved_flag']=bool(props.get('ServicesResolved',False))
    return result or {'operation':operation,'matching_response':False,'notification_count':count,'result':'timeout_or_unmatched; no retry or binding attempted'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=REQUESTS)
    p.add_argument('--target',required=True,type=Path);p.add_argument('--destination',required=True,type=Path)
    a=p.parse_args()
    try:print(json.dumps(run(a.operation,a.target,a.destination),indent=2));return 0
    except Exception as exc:
        print(json.dumps({'error_type':type(exc).__name__,'details_omitted':True}));return 2


if __name__=='__main__':raise SystemExit(main())
