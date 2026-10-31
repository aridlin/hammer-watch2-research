import binascii,struct
from tools.installer_simulator import InstallerReceiver
from tools.watch_face_install import frames
from tools.creek_inquiry import request_for,summarize_response
import pytest


def test_synthetic_receiver_requires_exact_fixture_and_verifies_crc():
    fixture=b'known fixture'*40;receiver=InstallerReceiver(fixture,'fixture01.bin')
    stream=list(frames(fixture))
    # Replace only the known test header filename for this simulation.
    start=stream[0][1][:11]+b'fixture01.bin\0'
    assert receiver.file_reply(start)==b'\xd1\0\0'
    for stage,packet,offset,crc in stream[1:]:
        ack=receiver.file_reply(packet)
        if stage=='data':assert ack==b'\xd2\0\0'+struct.pack('<II',offset,crc)
        else:assert ack==b'\xd4\0\0'
    assert receiver.completed and bytes(receiver.data)==fixture
    info=summarize_response('dial-info',receiver.inquiry_reply(request_for('dial-info')))
    assert info['crc16_valid'] and info['face_entry_count']==21
    receiver.file_reply(start)
    with pytest.raises(ValueError):receiver.file_reply(b'\xd2\0unexpected')


def test_exact_seeded_recovery_rejects_new_start_and_accepts_continuation():
    fixture=b'123456789'*100;receiver=InstallerReceiver(fixture,'fixture01.bin');receiver.seed_prefix(180)
    assert receiver.file_reply(b'\xd3\0')==b'\xd3\0\0'+struct.pack('<II',180,binascii.crc_hqx(fixture[:180],0))
    metadata=summarize_response('dial-info',receiver.inquiry_reply(request_for('dial-info')))
    assert metadata['face_entry_count']==21
    with pytest.raises(ValueError):receiver.file_reply(b'\xd1\0'+bytes(20))
    for offset in range(180,len(fixture),180):receiver.file_reply(b'\xd2\0'+fixture[offset:offset+180])
    assert receiver.file_reply(b'\xd4\0\0'+struct.pack('<I',binascii.crc_hqx(fixture,0)))==b'\xd4\0\0'
    assert receiver.completed
    full=InstallerReceiver(fixture,'fixture01.bin');full.seed_prefix(len(fixture))
    assert full.file_reply(b'\xd3\0')[3:7]==struct.pack('<I',len(fixture))
    assert full.file_reply(b'\xd4\0\0'+struct.pack('<I',binascii.crc_hqx(fixture,0)))==b'\xd4\0\0'
