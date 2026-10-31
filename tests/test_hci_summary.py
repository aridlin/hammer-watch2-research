import json
import pytest
from tools.hci_summary import summarize_rows,summarize_capture
from pathlib import Path


def test_capture_summary_never_exports_payload_or_identifiers():
    secret=b'private-token@example.invalid'
    value=bytes.fromhex('c109010100012800000000')+secret+b'\0\0'
    report=summarize_rows('1\t0x52\tc109010100010b000000000000\n2\t0x1b\t'+value.hex()+'\n3\t0x13\t\n')
    assert report['att_opcode_counts']=={'0x52':1,'0x1b':1,'0x13':1}
    output=json.dumps(report)
    assert secret.decode() not in output and secret.hex() not in output
    assert report['candidate_creek_start_headers'][1]['payload_omitted']


@pytest.mark.parametrize('row',['bad','x\t0x12\t00','1\tinvalid\t00','1\t0x12\tzz'])
def test_malformed_capture_rows(row):
    with pytest.raises(ValueError):summarize_rows(row)


def test_real_virtual_capture_notifications():
    p=Path('private/emulator/synthetic-05.btsnoop')
    if not p.exists():pytest.skip('Local virtual-radio capture absent')
    result=summarize_capture(p)
    assert result['att_opcode_counts']['0x1b']>=6
    assert result['att_opcode_counts']['0x52']>=2
