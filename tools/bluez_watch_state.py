"""Read cached BlueZ state/GATT UUIDs for one private target; never connect or write.

Run with system Python providing python-dbus. This does not pair, scan, call
Connect, read characteristic values, subscribe, or send proprietary commands.
"""
import argparse
import json
from pathlib import Path
import re
import stat


def load_target(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>4096:
        raise ValueError('Expected a bounded ordinary private target file')
    if stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('Target file must be private (0600)')
    target=json.loads(path.read_text())
    address=target.get('address','')
    if not isinstance(address,str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',address):
        raise ValueError('Invalid private target address')
    return address.upper()


def summarize(objects,address):
    matches=[(str(path),interfaces['org.bluez.Device1']) for path,interfaces in objects.items()
             if str(interfaces.get('org.bluez.Device1',{}).get('Address','')).upper()==address.upper()]
    if len(matches)>1:raise ValueError('Ambiguous target across adapters')
    if not matches:return {'present_in_bluez_cache':False,'identities_omitted':True}
    target,properties=matches[0]
    result={'present_in_bluez_cache':True,'identities_omitted':True,
            'state':{key:bool(properties.get(key,False)) for key in
                     ['Connected','Paired','Bonded','ServicesResolved','Blocked']},
            'advertised_uuids':sorted(str(u) for u in properties.get('UUIDs',[])),
            'gatt_services':[]}
    services={}
    for path,interfaces in objects.items():
        props=interfaces.get('org.bluez.GattService1')
        if props is not None and str(props.get('Device',''))==target:
            services[str(path)]={'uuid':str(props.get('UUID','')),'characteristics':[]}
    for interfaces in objects.values():
        props=interfaces.get('org.bluez.GattCharacteristic1')
        if props is not None and str(props.get('Service','')) in services:
            services[str(props['Service'])]['characteristics'].append({
                'uuid':str(props.get('UUID','')),'flags':sorted(str(f) for f in props.get('Flags',[]))})
    result['gatt_services']=sorted(services.values(),key=lambda x:x['uuid'])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--target',required=True,type=Path)
    a=p.parse_args()
    try:
        address=load_target(a.target)
        import dbus
        bus=dbus.SystemBus()
        manager=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager')
        print(json.dumps(summarize(manager.GetManagedObjects(),address),indent=2));return 0
    except (OSError,ValueError,ImportError):
        print(json.dumps({'error':'State unavailable; identities and exception details omitted'}));return 2


if __name__=='__main__':raise SystemExit(main())
