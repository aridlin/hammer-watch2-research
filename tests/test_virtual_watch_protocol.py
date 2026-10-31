import pytest
from tools.virtual_watch_protocol import varint, integer, blob, device_info, device_reply, fragment_reply
from tools.creek_frame import Header


def test_synthetic_proto_field_encoding():
    assert integer(1,2039)==bytes.fromhex('08f70f')
    assert blob(9,b'123456')==b'J\x06123456'
    assert len(device_info(minimal=True))==7
    assert device_info(minimal=True)==bytes.fromhex('08f70f1002200c')


@pytest.mark.parametrize('v',[-1,2**64,True,'1'])
def test_varint_rejects_invalid(v):
    with pytest.raises(ValueError):varint(v)


def test_reply_only_known_empty_device_request():
    request=bytes.fromhex('c10a010100010b000000000000')
    reply=device_reply(request,control=1,minimal=True)
    h=Header.parse(reply)
    assert h.sequence==138 and h.declared_length==18
    assert len(reply)==20 and reply[11:-2]==device_info(minimal=True)
    assert device_reply(request[:4]+b'\x01'+request[5:]) is None
    assert device_reply(request+b'\0') is None
    assert device_reply(b'\xc2'+request[1:]) is None


@pytest.mark.parametrize('mtu',[23,40,64,517])
def test_fragment_bounds_and_reconstruction(mtu):
    request=bytes.fromhex('c10a010100010b000000000000')
    reply=device_reply(request)
    parts=fragment_reply(reply,mtu)
    assert all(len(p)<=mtu-3 for p in parts)
    assert parts[0]+b''.join(p[2:] for p in parts[1:])==reply
    if len(parts)>1:
        assert parts[-1][:2]==b'\xc3\x8a'
        assert all(p[:2]==b'\xc2\x8a' for p in parts[1:-1])


@pytest.mark.parametrize('mtu',[0,22,518])
def test_invalid_mtu_refused(mtu):
    with pytest.raises(ValueError):fragment_reply(bytes(20),mtu)


def test_reassembly_of_real_shape_and_response_sequence_bit():
    from tools.virtual_watch_protocol import Reassembler,response_frame
    request=bytes.fromhex('c10a010100010b000000000000')
    reply=device_reply(request)
    r=Reassembler();parts=fragment_reply(reply,23)
    assert r.feed(parts[0]) is None
    assert r.feed(parts[1]) is None
    assert r.feed(parts[2])==reply
    assert not r.pending
    assert Header.parse(response_frame(request,b'\x08\x01')).sequence==0x8a
    with pytest.raises(ValueError):r.feed(b'\xc3\x01\x00')
    with pytest.raises(ValueError):r.feed(request+b'x')


def test_setup_replies_are_whitelisted_and_lab_framework_explicit():
    from tools.virtual_watch_protocol import setup_reply
    def request(main,sub=0):
        return Header(0xc1,7,1,1,sub,main,11,0).to_bytes()+b'\0\0'
    for main,sub in [(30,0),(21,0),(42,3),(34,0),(22,0)]:
        reply=setup_reply(request(main,sub))
        assert Header.parse(reply).sequence==0x87
        assert len(reply)==Header.parse(reply).declared_length+2
    assert setup_reply(request(99)) is None
    with pytest.raises(ValueError):setup_reply(request(22),lab_plate_version=0)


def test_observed_typed_request_has_no_trailer():
    from tools.virtual_watch_protocol import Reassembler,setup_reply
    # Genuine app MTU inquiry to the virtual watch, no personal content.
    request=bytes.fromhex('c11e010100220d000000000801')
    r=Reassembler()
    assert r.feed(request)==request
    assert setup_reply(request) is not None
    assert not r.pending


def test_normal_binding_only_and_private_fields_skipped():
    from tools.virtual_watch_protocol import setup_reply,selected_varints,Reassembler
    body=integer(1,1)+integer(2,0)+blob(4,b'private-user')+blob(5,b'private-account')
    request=Header(0xc1,7,1,1,0,5,11+len(body),0).to_bytes()+body
    r=Reassembler();parts=fragment_reply(request,23)
    for part in parts:result=r.feed(part)
    assert result==request
    reply=setup_reply(result)
    assert selected_varints(reply[11:-2],{1,2})=={1:1,2:2}
    assert b'private' not in reply
    encrypted=Header(0xc1,7,1,1,0,5,13,0).to_bytes()+integer(1,0)
    assert setup_reply(encrypted) is None


@pytest.mark.parametrize('data',[b'\x08\x80',b'\x12\x03x',b'\x00',b'\x0b',b'\x09x'])
def test_selected_varints_rejects_truncated_and_unknown_wire(data):
    from tools.virtual_watch_protocol import selected_varints
    with pytest.raises(ValueError):selected_varints(data,{1,2})


def test_observed_dial_inquiry_without_trailer():
    from tools.virtual_watch_protocol import Reassembler,setup_reply,selected_varints
    request=bytes.fromhex('c13c010100160d000000000800')
    assert Reassembler().feed(request)==request
    reply=setup_reply(request,lab_plate_version=9)
    assert selected_varints(reply[11:-2],{1,3,4})=={1:0,3:9,4:24}


def test_lab_profile_uses_confirmed_numeric_metadata_without_real_identifiers():
    from tools.virtual_watch_protocol import selected_varints
    data=device_info(lab_platform=3,lab_color=72,lab_identity=3)
    assert selected_varints(data,{1,6,21})=={1:2039,6:3,21:72}
    for values in [dict(lab_platform=4),dict(lab_color=256),dict(lab_identity=0)]:
        with pytest.raises(ValueError):device_info(**values)
