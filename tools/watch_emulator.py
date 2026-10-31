"""Creek research peer confined to Android Netsim's virtual radio.

Service/characteristic UUIDs are confirmed by physical GATT discovery. Default mode is discovery-only. Opt-in synthetic device-info responses are
validated through device identification; setup remains an experiment.
No complete protocol emulation is claimed.
"""
import argparse
import asyncio
import json
from pathlib import Path
import time
import os
import logging
from contextlib import contextmanager
import fcntl


def validate_transport(value):
    if value=='android-netsim':return value
    if value.startswith(('android-netsim:localhost:', 'android-netsim:127.0.0.1:')):
        suffix=value.rsplit(':',1)[-1]
        if suffix.isdigit() and 1<=int(suffix)<=65535:return value
    raise ValueError('Only local Android Netsim transport is permitted; physical radios are forbidden')


@contextmanager
def exclusive_peer(path):
    """Keep duplicate lab peers from advertising the same synthetic identity."""
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
    try:
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another local virtual peer is running') from None
        yield
    finally:os.close(fd)


async def run(args):
    from bumble.core import AdvertisingData
    from bumble.device import Device
    from bumble.gatt import Characteristic,CharacteristicValue,Service
    from bumble.hci import Address
    from bumble.transport import open_transport
    validate_transport(args.transport)
    if args.duration<=0 or args.duration>3600:raise ValueError('Duration must be 1..3600 seconds')
    if args.log.exists():raise FileExistsError('Refusing to overwrite emulator events')
    args.log.parent.mkdir(parents=True,exist_ok=True)
    if args.synthetic_device_info:
        debug_path=args.log.with_suffix('.debug.log')
        if debug_path.exists():raise FileExistsError('Refusing debug-log overwrite')
        fd=os.open(debug_path,os.O_WRONLY | os.O_CREAT | os.O_EXCL,0o600)
        logging.basicConfig(stream=os.fdopen(fd,'w'),level=logging.DEBUG)
    with os.fdopen(os.open(args.log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as log:
        def event(kind,**fields):
            log.write(json.dumps({'time_monotonic':time.monotonic(),'event':kind,**fields})+'\n');log.flush()
        async with await open_transport(args.transport) as transport:
            device=Device.with_hci(args.name,Address(f'F2:F1:F0:00:00:{args.lab_identity:02X}'),transport.source,transport.sink)
            from tools.virtual_watch_protocol import Reassembler
            requests=Reassembler()
            tasks=set()
            def finished(task):
                tasks.discard(task)
                if not task.cancelled() and task.exception() is not None:
                    event('synthetic_reply_error',error_type=type(task.exception()).__name__)
            async def send_reply(connection,value):
                await asyncio.sleep(0.2)
                if args.synthetic_device_info:
                    from tools.virtual_watch_protocol import device_reply,fragment_reply,setup_reply
                    reply=(setup_reply(bytes(value),args.lab_dial_framework,args.lab_platform,args.lab_device_color,args.lab_identity) if args.synthetic_setup
                           else device_reply(bytes(value),args.reply_control,args.minimal_device_info,args.lab_platform,args.lab_device_color,args.lab_identity))
                    if reply is not None:
                        event('subscription_state',cccd=device.gatt_server.read_cccd(connection,notify).hex())
                        parts=fragment_reply(reply,connection.att_mtu)
                        for part in parts:
                            await device.notify_subscriber(connection,notify,part)
                            await asyncio.sleep(0.03)
                        event('synthetic_reply',size=len(reply),command_main=value[5],command_sub=value[4],fragments=len(parts),att_mtu=connection.att_mtu)

            def received(connection,value):
                event('gatt_write',size=len(value),hex=bytes(value).hex())
                if args.synthetic_device_info:
                    try:message=requests.feed(bytes(value))
                    except ValueError:
                        event('reassembly_rejected');return
                    if message is not None:
                        task=asyncio.create_task(send_reply(connection,message))
                        tasks.add(task);task.add_done_callback(finished)
            notify=Characteristic('00000002-0000-1000-8000-00805f9b34fb',
                Characteristic.Properties.NOTIFY|Characteristic.Properties.READ,
                Characteristic.READABLE,b'')
            write=Characteristic('00000001-0000-1000-8000-00805f9b34fb',
                Characteristic.Properties.WRITE|Characteristic.Properties.WRITE_WITHOUT_RESPONSE,
                Characteristic.WRITEABLE,CharacteristicValue(write=received))
            device.add_service(Service('00000ff0-0000-1000-8000-00805f9b34fb',[notify,write]))
            device.on('connection',lambda connection:event('connection'))
            await device.power_on()
            adv=bytes(AdvertisingData([(AdvertisingData.FLAGS,b'\x06'),
                (AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS,b'\xf0\x0f')]))
            scan=bytes(AdvertisingData([(AdvertisingData.COMPLETE_LOCAL_NAME,args.name.encode('utf-8'))]))
            if len(scan)>31:raise ValueError('Advertisement name is too long')
            await device.start_advertising(advertising_data=adv,scan_response_data=scan,auto_restart=True)
            event('advertising',name=args.name,mode='synthetic_device_info' if args.synthetic_device_info else 'discovery_only_no_protocol_replies')
            print(json.dumps({'status':'advertising_on_virtual_radio','log':str(args.log)}),flush=True)
            await asyncio.sleep(args.duration)
            await device.stop_advertising()
            for task in tasks:task.cancel()
            if tasks:await asyncio.gather(*tasks,return_exceptions=True)
            event('stopped')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--transport',default='android-netsim')
    p.add_argument('--name',default='HW2')
    p.add_argument('--duration',type=int,default=300)
    p.add_argument('--log',type=Path,required=True)
    p.add_argument('--synthetic-device-info',action='store_true',help='Local-only experimental protobuf device response; capabilities are synthetic')
    p.add_argument('--minimal-device-info',action='store_true',help='Probe only ID/version in a single 20-byte reply')
    p.add_argument('--synthetic-setup',action='store_true',help='Opt-in schema-based virtual setup replies; never physical capability evidence')
    p.add_argument('--lab-dial-framework',type=int,choices=range(1,10),default=9,help='Synthetic framework version for lab catalog exploration only')
    p.add_argument('--lab-platform',type=int,choices=range(4),default=0)
    p.add_argument('--lab-device-color',type=int,choices=range(256),default=0)
    p.add_argument('--lab-identity',type=int,choices=range(1,255),default=2)
    p.add_argument('--reply-control',type=int,choices=[1,2],default=2)
    a=p.parse_args()
    if a.synthetic_setup:a.synthetic_device_info=True
    try:
        with exclusive_peer(Path(__file__).resolve().parents[1]/'private/emulator/peer.lock'):
            asyncio.run(run(a))
        return 0
    except (ValueError,OSError,ImportError) as exc:
        print(json.dumps({'error_type':type(exc).__name__,'message':str(exc)}));return 2


if __name__=='__main__':raise SystemExit(main())
