"""Synthetic receiver for Android Netsim only; never connect this to hardware."""
import binascii,struct
from .creek_frame import Header
from .virtual_watch_protocol import integer,blob,response_frame,device_info


class InstallerReceiver:
    def __init__(self,expected,filename):
        if not 0<len(expected)<=1048576 or '/' in filename:raise ValueError('Invalid synthetic fixture')
        self.expected=expected;self.filename=filename.encode();self.data=bytearray();self.started=False;self.completed=False;self.reject_new_start=False

    def seed_prefix(self,offset):
        if not 0<offset<=len(self.expected) or (offset%180 and offset!=len(self.expected)):raise ValueError('Invalid simulated checkpoint')
        self.data=bytearray(self.expected[:offset]);self.started=True;self.completed=False;self.reject_new_start=True

    def file_reply(self,packet):
        if len(packet)<2:return None
        opcode=packet[0]
        if opcode==0xd1:
            if self.reject_new_start:raise ValueError('Recovery must not send a new D1')
            if len(packet)<12 or packet[1]!=0 or struct.unpack_from('<II',packet,2)!=(len(self.expected),len(self.expected)) or packet[10]!=1 or packet[11:]!=self.filename+b'\0':raise ValueError('Unexpected synthetic file start')
            self.started=True;self.completed=False;self.data.clear();return b'\xd1\0\0'
        if opcode==0xd3 and packet==b'\xd3\0' and self.started:
            return b'\xd3\0\0'+struct.pack('<II',len(self.data),binascii.crc_hqx(self.data,0))
        if opcode==0xd2 and self.started and not self.completed:
            part=packet[2:];offset=len(self.data)
            if not part or self.expected[offset:offset+len(part)]!=part:raise ValueError('Synthetic payload differs')
            self.data.extend(part);return b'\xd2\0\0'+struct.pack('<II',len(self.data),binascii.crc_hqx(self.data,0))
        if opcode==0xd4 and self.started:
            if bytes(self.data)!=self.expected or packet!=b'\xd4\0\0'+struct.pack('<I',binascii.crc_hqx(self.data,0)):raise ValueError('Synthetic end checksum mismatch')
            self.completed=True;return b'\xd4\0\0'
        return None

    def inquiry_reply(self,packet):
        header=Header.parse(packet);command=(header.command_byte_1,header.command_byte_0)
        if command==(1,0):body=device_info(lab_platform=3,lab_color=72,lab_identity=4)
        elif command==(22,0):
            body=integer(3,8)+integer(4,24)+integer(11,41943040)+integer(12,2097152)+integer(15,4)+integer(18,24)
            for i in range(20):body+=blob(10,integer(1,1)+blob(4,f'synthetic_{i:02}.bin'.encode()))
            if self.started:body+=blob(10,integer(1,1)+blob(4,self.filename))
            if self.completed:body+=blob(14,self.filename)
        elif command==(34,0):body=integer(1,1)+integer(2,244)+integer(8,1)
        else:return None
        reply=response_frame(packet,body)[:-2];return reply+binascii.crc_hqx(reply,0xffff).to_bytes(2,'little')
