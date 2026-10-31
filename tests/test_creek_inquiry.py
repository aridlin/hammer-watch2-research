import pytest
from tools.creek_inquiry import request_for,summarize_response,byte_fields
from tools.virtual_watch_protocol import response_frame as synthetic_response,integer,blob
import binascii

def response_frame(request,body):
    packet=synthetic_response(request,body)[:-2]
    return packet+binascii.crc_hqx(packet,0xffff).to_bytes(2,'little')


def test_only_fixed_read_only_requests_and_redaction():
    with pytest.raises(ValueError):request_for('bind')
    with pytest.raises(ValueError):request_for('upload')
    req=request_for('device-info')
    body=integer(1,2039)+integer(2,2)+integer(4,12)+blob(9,b'private-mac')+blob(19,integer(1,466)+integer(2,466))+blob(32,b'private-account')
    result=summarize_response('device-info',response_frame(req,body))
    assert result['present_numeric_fields']['device_id']==2039
    assert result['display']=={'1':466,'2':466}
    assert 'private' not in str(result)
    with pytest.raises(ValueError):summarize_response('dial-info',response_frame(req,body))


def test_dial_safe_summary_unknown_fields_and_invalid_lengths():
    body=integer(3,9)+integer(15,4)+blob(14,b'personal-face-name')+blob(10,integer(2,5)+blob(4,b'ewrcompass_0819@LC'))
    packet=response_frame(request_for('dial-info'),body)
    r=summarize_response('dial-info',packet)
    assert r['present_numeric_fields']['framework_version']==9
    assert r['adventurer_entry_present'] and not r['active_is_acquired_adventurer']
    assert 'personal' not in str(r)
    with pytest.raises(ValueError):summarize_response('dial-info',packet[:-1])
    for data in [b'\x12\x05x',b'\x08\x80',b'\x00',b'\x0b']:
        with pytest.raises(ValueError):byte_fields(data,{2})


def test_crc_rejection_and_real_replies_when_available():
    from pathlib import Path
    from tools.virtual_watch_protocol import Reassembler
    import json
    packet=response_frame(request_for('dial-info'),integer(3,8))
    with pytest.raises(ValueError):summarize_response('dial-info',packet[:-1]+bytes([packet[-1]^1]))
    count=0
    for kind,operation in [('device','device-info'),('dial','dial-info')]:
        path=Path(f'private/emulator/physical-{kind}-inquiry-01.jsonl')
        if not path.exists():continue
        assembler=Reassembler()
        for line in path.read_text().splitlines():
            event=json.loads(line)
            if event['event']=='notification':
                complete=assembler.feed(bytes.fromhex(event['hex']))
                if complete:
                    assert summarize_response(operation,complete)['crc16_valid'];count+=1
    if not count:pytest.skip('Private real inquiry replies not supplied')
