"""Offline inspector/reconstructor for the observed SDK D1/D2/D4 transfer variant.

Validated against virtual official-app writes, not physical transfer replies.
No radio access or sending methods. Unknown header bytes remain uninterpreted.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
from .hammer_re import checked_path

LIMIT=1024*1024


def parse_value(data):
    if not 2<=len(data)<=514:raise ValueError('Invalid observed ATT value size')
    opcode=data[0];result={'opcode':f'{opcode:02x}','header_byte_1':data[1],'bytes':len(data)}
    if opcode==0xd1:
        if len(data)<12 or len(data)>42 or data[-1]!=0:raise ValueError('Truncated/oversized start filename')
        size,original=struct.unpack_from('<II',data,2)
        if not 0<size<=LIMIT or not 0<original<=LIMIT:raise ValueError('Transfer size exceeds bounds')
        name=data[11:-1]
        if not name or b'\0' in name:raise ValueError('Invalid observed filename')
        result.update(stage='start',transfer_bytes=size,original_bytes=original,
                      parameter_byte=data[10],filename_sha256=hashlib.sha256(name).hexdigest(),
                      known_adventurer_name=name==b'ewrcompass_0819@LC.bin')
    elif opcode==0xd2:result.update(stage='data',payload_bytes=len(data)-2)
    elif opcode==0xd4:
        if len(data)!=7:raise ValueError('Unknown end-packet shape')
        result.update(stage='end',reserved_byte=data[2],checksum=struct.unpack_from('<I',data,3)[0])
    elif opcode==0xd3:result.update(stage='query_index')
    else:raise ValueError('Not an observed upload opcode')
    return result


def reconstruct_events(path):
    path=checked_path(path)
    if path.stat().st_size>32*1024*1024:raise ValueError('Capture exceeds bounds')
    payload=bytearray();start=None;complete=[];packets=0;invalid_starts=0
    for line in path.read_text().splitlines():
        event=json.loads(line)
        if event.get('event')!='gatt_write':continue
        data=bytes.fromhex(event['hex'])
        if not data or data[0] not in (0xd1,0xd2,0xd3,0xd4):continue
        try:info=parse_value(data)
        except ValueError:
            if data[0]==0xd1:invalid_starts+=1;start=None;payload.clear();continue
            raise
        if info['stage']=='start':start=info;payload.clear();packets=0
        elif info['stage']=='data' and start:
            payload.extend(data[2:]);packets+=1
            if len(payload)>start['transfer_bytes']:raise ValueError('Data exceeds advertised size')
        elif info['stage']=='end' and start:
            if len(payload)!=start['transfer_bytes']:raise ValueError('Incomplete transfer')
            calculated=binascii.crc_hqx(payload,0)
            if calculated!=info['checksum']:raise ValueError('Transfer CRC16/XMODEM mismatch')
            complete.append((bytes(payload),{'start':start,'end':info,'data_packet_count':packets,
                             'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),
                             'crc16_xmodem_valid':True,'physical_transfer_tested':False}))
            start=None;payload.clear()
    return complete,{'invalid_or_truncated_starts':invalid_starts,'incomplete_final_bytes':len(payload)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('events',type=Path)
    p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args()
    try:
        samples,notes=reconstruct_events(a.events)
        if not samples:raise ValueError('No complete validated virtual upload found')
        data,report=samples[-1]
        with a.destination.open('xb') as f:f.write(data)
        print(json.dumps({'last_completed_transfer':report,'capture_notes':notes},indent=2));return 0
    except (ValueError,OSError,KeyError):
        print(json.dumps({'error':'Invalid or incomplete observed transfer; raw payloads omitted'}));return 2


if __name__=='__main__':raise SystemExit(main())
