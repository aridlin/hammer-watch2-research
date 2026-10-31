import pytest
from tools.creek_frame import Header


def test_observed_app_initialization_header():
    # Exact app-side request to a synthetic Netsim peer; no user/device data.
    packet = bytes.fromhex('c128010100010b000000000000')
    h = Header.parse(packet)
    assert (h.type_byte,h.sequence,h.flags,h.control) == (0xc1,40,1,1)
    assert (h.command_byte_0,h.command_byte_1,h.declared_length,h.code) == (0,1,11,0)
    assert h.to_bytes() == packet[:11]
    info = h.summary(len(packet))
    assert info['bytes_after_header'] == 2
    assert info['length_semantics'] == 'unresolved'
    assert 'payload_hex' not in info


@pytest.mark.parametrize('n',range(11))
def test_truncated_header(n):
    with pytest.raises(ValueError): Header.parse(bytes(n))


def test_unknown_fields_are_losslessly_preserved():
    packet = bytes.fromhex('fffeab99aaffffffffffee')
    h = Header.parse(packet)
    assert h.to_bytes() == packet
    assert h.summary(len(packet))['type_name'] == 'unknown'
    with pytest.raises(ValueError): Header(256,0,0,0,0,0,0,0).to_bytes()
