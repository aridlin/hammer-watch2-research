"""Synthetic device-info oracle for local Netsim experiments only.

Fields follow the pinned Creek deviceinfo.pb.swift schema. Model/version come
from user screenshots; platform and capabilities are deliberately synthetic.
This module cannot connect to radios or transmit packets by itself.
"""
from tools.creek_frame import Header


def varint(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError('Expected uint64')
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128); value >>= 7
    out.append(value)
    return bytes(out)


def integer(field, value):
    if not 1 <= field < 2**29: raise ValueError('Invalid protobuf field')
    return varint(field << 3) + varint(value)


def blob(field, data):
    if not isinstance(data, bytes) or len(data) > 4096: raise ValueError('Invalid bounded bytes')
    return varint(field << 3 | 2) + varint(len(data)) + data


def device_info(minimal=False,lab_platform=0,lab_color=0,lab_identity=2):
    if lab_platform not in range(4) or not 0<=lab_color<=255 or not 1<=lab_identity<=254:
        raise ValueError('Invalid synthetic profile')
    if minimal:return integer(1,2039)+integer(2,2)+integer(4,12)
    size = integer(1, 466) + integer(2, 466) + integer(3, 233)
    return (integer(1, 2039) + integer(2, 2) + integer(4, 12)
            + integer(7, 1) + blob(9, bytes.fromhex('f2f1f00000')+bytes([lab_identity]))
            + blob(11, integer(3, 80)) + blob(19, size)
            + integer(27, 2)+integer(6,lab_platform)+integer(21,lab_color))


def device_reply(request, control=2, minimal=False,lab_platform=0,lab_color=0,lab_identity=2):
    h = Header.parse(request)
    if h.type_byte != 0xc1 or (h.command_byte_0,h.command_byte_1) != (0,1):
        return None
    if len(request) != 13 or h.declared_length != 11:
        return None
    data = device_info(minimal,lab_platform,lab_color,lab_identity)
    # CreekGlobalNotice masks bit 7 for reassembly but routes values <=127
    # to unsolicited UpdateNotice; request callbacks require the response bit.
    # Control/trailer remain experiments until runtime acceptance is seen.
    return Header(0xc1,h.sequence | 0x80,1,control,0,1,11+len(data),0).to_bytes() + data + b'\0\0'


def fragment_reply(packet, att_mtu):
    """Experimental app-style C1 / C2 / C3 framing from seedData assembly."""
    if not 23 <= att_mtu <= 517 or len(packet) > 4096:
        raise ValueError('Invalid bounded virtual packet/MTU')
    # ATT attribute values are capped at 512 bytes even at negotiated MTU517.
    size=min(att_mtu-3,512)
    if len(packet)<=size:return [packet]
    out=[packet[:size]]
    tail=packet[size:]
    while tail:
        part,tail=tail[:size-2],tail[size-2:]
        out.append(bytes((0xc2 if tail else 0xc3,packet[1]))+part)
    return out


class Reassembler:
    """Bounded reassembly of observed app-style C1/C2/C3 virtual requests."""
    def __init__(self):
        self.pending={}

    def feed(self, packet):
        if len(packet)<2 or len(packet)>514:raise ValueError('Invalid virtual ATT value size')
        key=packet[1]&0x7f
        if packet[0]==0xc1:
            h=Header.parse(packet)
            if not 11<=h.declared_length<=4096:raise ValueError('Virtual message exceeds bounds')
            if len(self.pending)>=32 and key not in self.pending:raise ValueError('Too many pending messages')
            self.pending[key]=bytearray(packet)
        elif packet[0] in (0xc2,0xc3):
            if key not in self.pending:raise ValueError('Orphan continuation')
            self.pending[key].extend(packet[2:])
        else:return None
        data=self.pending[key]
        head=Header.parse(data)
        # The app's typed outgoing protobuf requests omit the two-byte trailer;
        # empty inquiries and the observed incoming response form include it.
        no_trailer={(34,0),(30,1),(4,0),(2,0),(3,0),(5,0),(22,0)}
        typed_request=(not head.sequence&0x80 and
                       (head.command_byte_1,head.command_byte_0) in no_trailer
                       and head.declared_length>11)
        expected=head.declared_length+(0 if typed_request else 2)
        if len(data)>expected:
            del self.pending[key];raise ValueError('Virtual message exceeds declared length')
        if len(data)==expected:
            del self.pending[key]
            return bytes(data)
        return None


def response_frame(request, body):
    h=Header.parse(request)
    if len(body)>4096:raise ValueError('Synthetic body too large')
    return Header(0xc1,h.sequence|0x80,1,h.control,h.command_byte_0,
                  h.command_byte_1,11+len(body),0).to_bytes()+body+b'\0\0'


def setup_reply(request, lab_plate_version=9,lab_platform=0,lab_color=0,lab_identity=2):
    """Whitelisted schema-based lab replies, never physical capability claims."""
    h=Header.parse(request)
    cmd=(h.command_byte_1,h.command_byte_0)
    if cmd==(1,0):return device_reply(request,h.control,False,lab_platform,lab_color,lab_identity)
    if cmd==(34,0): # mtu.pb.swift: operate, get_tran_mtu_size, BLE PRN
        body=integer(1,1)+integer(2,30)+integer(8,1)
    elif cmd==(5,0): # binding.pb.swift: only documented normal bind, virtual peer
        fields=selected_varints(request[11:h.declared_length],{1,2})
        if fields.get(1,0)!=1:return None
        body=integer(1,1)+integer(2,2)
    elif cmd==(30,0): # table.pb.swift: explicit default disturb submessage
        body=blob(1,b'')
    elif cmd==(30,1): # appTable.pb.swift: no optional app features advertised
        body=integer(1,0)
    elif cmd==(4,0): # language.pb.swift: inquire, English, supported English
        body=integer(1,1)+integer(2,1)+integer(4,1)
    elif cmd==(2,0): # time.pb.swift: acknowledge virtual time setting
        body=integer(1,2)
    elif cmd==(3,0): # userinfo.pb.swift: acknowledge virtual user setting
        body=integer(2,2)
    elif cmd==(21,0): # sport.pb.swift: empty supported sport set
        body=integer(1,0)
    elif cmd==(42,3): # alexa.pb.swift: voice-assistant support disabled
        body=integer(1,0)
    elif cmd==(22,0): # watchdial.pb.swift: explicitly simulated capabilities
        if type(lab_plate_version) is not int or not 1<=lab_plate_version<=9:
            raise ValueError('Invalid lab framework version')
        body=(integer(1,0)+integer(3,lab_plate_version)+integer(4,24)
              +integer(6,1)+integer(8,1)+integer(11,40*1024*1024)+integer(15,4)
              +integer(17,3)+integer(18,24))
    else:return None
    return response_frame(request,body)


def selected_varints(data, allowed):
    """Read selected numeric protobuf fields; skip all private bytes fields."""
    if len(data)>4096:raise ValueError('Protobuf exceeds bounds')
    pos=0;out={}
    def read():
        nonlocal pos
        value=0
        for shift in range(0,70,7):
            if pos>=len(data):raise ValueError('Truncated varint')
            b=data[pos];pos+=1;value|=(b&127)<<shift
            if b<128:
                if value>=2**64:raise ValueError('Varint overflow')
                return value
        raise ValueError('Varint overflow')
    while pos<len(data):
        tag=read();field,wire=tag>>3,tag&7
        if not field:raise ValueError('Invalid field')
        if wire==0:
            value=read()
            if field in allowed:out[field]=value
        elif wire==2:
            size=read();pos+=size
        elif wire==1:pos+=8
        elif wire==5:pos+=4
        else:raise ValueError('Unsupported wire type')
        if pos>len(data):raise ValueError('Truncated field')
    return out
