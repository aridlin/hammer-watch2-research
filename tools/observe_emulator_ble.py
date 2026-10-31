"""BLE observer validated on the ARM64-translated app using chunked loading.

Observe fixed BLE event names/sizes in the project's debug emulator only.
Opt-in virtual-* modes actively negotiate/emulate fixed Netsim identity04;
they are not passive observers and cannot prove physical watch behavior.

Requires a loopback Frida server forwarded via tools/adb-debug to port 27043.
No arguments/payloads, addresses, user IDs or credentials are recorded.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'OnCharacteristicChanged','WriteCharacteristicResponse','SetNotificationResponse',
         'DiscoverServicesResult','DeviceState','observer_ready','virtual_mtu_requested','virtual_start_ack_injected','virtual_transfer_start','virtual_transfer_progress','virtual_transfer_end','virtual_transfer_probe_error'}


def sanitized_event(message):
    payload=message.get('payload')
    if message.get('type')!='send' or not isinstance(payload,dict):return None
    event=payload.get('event')
    if event not in ALLOWED:return None
    result={'event':event}
    if type(payload.get('size')) is int and 0<=payload['size']<=1024*1024:
        result['size']=payload['size']
    return result


def adb(*args):
    return subprocess.check_output([str(ROOT/'tools/adb-debug'),*args],timeout=20,text=True).strip()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['observe','virtual-mtu','virtual-start-ack','virtual-transfer'],default='observe',help='virtual-mtu requests ATT517 for fixed Netsim identity04 only')
    p.add_argument('--duration',type=int,default=180)
    p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args()
    if not 1<=a.duration<=1800:raise ValueError('Duration out of bounds')
    if not a.destination.resolve().is_relative_to(ROOT/'private/emulator'):
        raise ValueError('Observer outputs must remain private/emulator')
    if adb('shell','getprop','ro.kernel.qemu')!='1':raise ValueError('Not an emulator')
    if adb('shell','getprop','ro.build.type')!='userdebug':raise ValueError('Not a debug build')
    pid_text=adb('shell','pidof','com.hammerup.app')
    if not pid_text.isdigit():raise ValueError('Expected one HAMMER App process')
    import frida
    device=frida.get_device_manager().add_remote_device('127.0.0.1:27043')
    session=device.attach(int(pid_text))
    bundle={'observe':'observe-ble.js','virtual-mtu':'request-virtual-mtu.js','virtual-start-ack':'virtual-start-ack.js','virtual-transfer':'virtual-transfer.js'}[a.mode]
    source=(ROOT/'private/frida-observer'/bundle).read_text()
    if len(source)>2*1024*1024:raise ValueError('Observer bundle too large')
    # Large create_script RPCs close this host's transport. Transfer bounded
    # source chunks to the agent, then evaluate locally in the emulator.
    bootstrap='let src="";rpc.exports={chunk(s){src+=s;},run(){(0,eval)(src);src="";}};'
    script=session.create_script(bootstrap,runtime='v8')
    with os.fdopen(os.open(a.destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as log:
        def receive(message,data):
            result=sanitized_event(message)
            if result:
                result['time_monotonic']=time.monotonic()
                log.write(json.dumps(result)+'\n');log.flush()
            elif message.get('type')=='error':
                log.write(json.dumps({'event':'observer_script_error'})+'\n');log.flush()
        script.on('message',receive)
        try:
            script.load()
            for start in range(0,len(source),32768):
                script.exports_sync.chunk(source[start:start+32768])
            script.exports_sync.run()
            print(json.dumps({'observer':'attached_to_debug_emulator_app','payload_logging':False}),flush=True)
            time.sleep(a.duration)
        finally:
            script.unload();session.detach()
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,subprocess.SubprocessError):
        print(json.dumps({'error':'Observer unavailable; no data or exception details printed'}));raise SystemExit(2)
    except Exception as exc:
        if type(exc).__module__.startswith(('frida','_frida')):
            print(json.dumps({'error':'Frida attachment failed; observer not running'}));raise SystemExit(2)
        raise
