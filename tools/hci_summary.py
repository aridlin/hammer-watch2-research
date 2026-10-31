"""Offline HCI/ATT summary with no addresses, identities or payload exports.

Requires tshark. Raw captures must stay private. Header candidates are reported
only for C1 packets; C2/C3 fragments are counted without interpreting their body.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from tools.creek_frame import Header


def summarize_rows(text):
    counts=Counter(); lengths=Counter(); candidates=[]
    for line in text.splitlines():
        fields=line.split('\t')
        if len(fields)!=3:raise ValueError('Unexpected tshark row')
        number,opcode,value=fields
        if not number.isdigit() or not opcode.startswith('0x'):
            raise ValueError('Invalid packet metadata')
        int(opcode,16); counts[opcode]+=1
        if not value:continue
        if len(value)>131072:raise ValueError('Oversized ATT value')
        packet=bytes.fromhex(value)
        lengths[str(len(packet))]+=1
        if opcode in ('0x1b','0x52','0x12') and len(packet)>=13 and packet[0]==0xc1:
            h=Header.parse(packet)
            if 11<=h.declared_length<=8*1024*1024:
                candidates.append({'frame':int(number),'opcode':opcode,**h.summary(len(packet))})
    return {'att_opcode_counts':dict(counts),'value_size_histogram':dict(lengths),
            'candidate_creek_start_headers':candidates,
            'payloads_and_identities_omitted':True,
            'reassembly_and_crc_validation':False}


def summarize_capture(path):
    path=Path(path)
    if path.stat().st_size>256*1024*1024:raise ValueError('Capture exceeds limit')
    result=subprocess.run(['tshark','-n','-r',str(path.resolve()),'-Y','btatt',
        '-T','fields','-e','frame.number','-e','btatt.opcode','-e','btatt.value'],
        capture_output=True,text=True,timeout=60,check=True)
    summary=summarize_rows(result.stdout)
    with path.open('rb') as f:summary['capture_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path)
    a=p.parse_args()
    try:
        print(json.dumps(summarize_capture(a.capture),indent=2));return 0
    except (OSError,ValueError,subprocess.SubprocessError):
        print(json.dumps({'error':'Unable to summarize capture; diagnostic payloads omitted'}));return 2


if __name__=='__main__':raise SystemExit(main())
