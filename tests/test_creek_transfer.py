import binascii,json,struct
from pathlib import Path
import pytest
from tools.creek_transfer import parse_value,reconstruct_events


def test_bounded_reconstruction_and_crc_rejection(tmp_path):
    data=b'example-offline-payload'
    start=b'\xd1\0'+struct.pack('<II',len(data),len(data))+b'\x01ewrcompass_0819@LC.bin\0'
    end=b'\xd4\0\0'+struct.pack('<I',binascii.crc_hqx(data,0))
    packets=[start,b'\xd2\0'+data[:8],b'\xd2\0'+data[8:],end]
    path=tmp_path/'events.jsonl'
    def save():path.write_text(''.join(json.dumps({'event':'gatt_write','hex':p.hex()})+'\n' for p in packets))
    save();samples,notes=reconstruct_events(path)
    assert samples[0][0]==data and samples[0][1]['crc16_xmodem_valid']
    assert samples[0][1]['data_packet_count']==2
    assert 'ewrcompass' not in str(samples[0][1])
    packets[-1]=end[:-1]+b'\x01';save()
    with pytest.raises(ValueError):reconstruct_events(path)
    for bad in [b'',b'\xd1\0',b'\xd4\0',bytes(515),b'\xc1\0']:
        with pytest.raises(ValueError):parse_value(bad)


def test_real_virtual_upload_when_available():
    path=Path('private/emulator/transfer-peer-02.jsonl')
    if not path.exists():pytest.skip('Private real SDK virtual capture not supplied')
    samples,_=reconstruct_events(path)
    if not samples:pytest.skip('Full virtual capture not yet available')
    original=Path('faces/local/adventurer/official-color72.bin')
    assert samples[-1][0]==original.read_bytes()
