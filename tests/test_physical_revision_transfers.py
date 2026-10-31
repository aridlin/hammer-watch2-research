"""Replay private real ACKs against independently computed candidate CRCs."""
import binascii,json
from pathlib import Path
import pytest
from tools.watch_face_install import validate_ack
from tools.adventurer_digital import TEST_NAMES

@pytest.mark.parametrize('revision,directory',[(3,'physical-seconds-no-meters-02'),(4,'physical-hands-date-rim-01'),(5,'physical-weather-font-01'),(6,'physical-polish-weather-01'),(7,'physical-smaller-time-lower-date-01')])
def test_real_acknowledgments_match_source_bytes(revision,directory):
    log=Path('private/emulator')/directory/'upload.jsonl'
    binary=Path('faces/local/adventurer')/(TEST_NAMES[revision]+'.bin')
    if not log.exists() or not binary.exists():pytest.skip('Private physical capture absent')
    data=binary.read_bytes();sent=None;acks=0;complete=False
    for line in log.read_text().splitlines():
        event=json.loads(line)
        if event['event']=='send':sent=event
        elif event['event']=='ack':
            packet=bytes.fromhex(event['hex']);stage=sent['stage'];offset=sent['offset']
            expected_opcode={'start':0xd1,'data':0xd2,'end':0xd4}[stage]
            validate_ack(packet,expected_opcode,stage,offset,binascii.crc_hqx(data[:offset],0));acks+=1
        elif event['event']=='transfer_acknowledged':complete=True
    assert complete and acks==2+(len(data)+179)//180
