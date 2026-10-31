"""Reproduce selected native-library observations without executing app code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .hammer_re import checked_path

# Fixed public identifiers only. This is deliberately not a general secret/string dump.
NEEDLES = [
    'https://app.hammerphones.com',
    '/service-parts/v1/dial/classify/isUpdate',
    '/service-parts/v1/dial/classify/pb/list',
    '/service-parts/v1/dial/listFirmware',
    '/service-parts/v1/dial/pages',
    '/service-parts/v1/dial/profile',
    'package:creek_dial_sdk/creek_custom_dial_sdk.dart',
    'package:creek_dial_sdk/creek_photo_dial_sdk.dart',
    'package:creek_dial_sdk/dial/model/dial_json_model.dart',
    'package:creek_dial_sdk/dial/dial_tool.dart',
    'package:creek_dial_sdk/byte_array/byte_array.dart',
    'package:creek_app/app/datas/manager/network/request/device/dial_list.dart',
    'dial.json', '00000FF0-0000-1000-8000-00805f9b34fb',
    '00002902-0000-1000-8000-00805f9b34fb',
]


def recon(libapp, resource_lib=None):
    p=checked_path(libapp);raw=p.read_bytes()
    result={'schema_version':1,'library_sha256':hashlib.sha256(raw).hexdigest(),
            'evidence_type':'static byte-string occurrences; not executed call traces',
            'observations':[]}
    for value in NEEDLES:
        offset=raw.find(value.encode('ascii'))
        if offset>=0:result['observations'].append({'literal':value,'file_offset':offset})
    if resource_lib:
        p=checked_path(resource_lib)
        proc=subprocess.run(['nm','-D','--defined-only',str(p)],capture_output=True,text=True,timeout=20,check=True)
        symbols=[]
        for line in proc.stdout.splitlines():
            fields=line.split()
            if len(fields)==3 and fields[2].startswith('Java_com_actions_actres_'):
                symbols.append({'address_hex':fields[0],'name':fields[2]})
        result['resource_library']={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'jni_exports':symbols}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('libapp');p.add_argument('--resource-lib');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.output.exists():raise FileExistsError('Output already exists')
        result=recon(a.libapp,a.resource_lib)
        with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
        return 0
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print(json.dumps({'error_type':type(exc).__name__}),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
