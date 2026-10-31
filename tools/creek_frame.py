"""Offline inspection of the observed 11-byte Creek app header.

This does not reassemble fragments, verify integrity, interpret payloads or send
commands. Length semantics beyond the recovered uint32 are still unresolved.
"""
import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import struct

HEADER = struct.Struct('<BBBBBBIB')
TYPES = {0xC1: 'start', 0xC2: 'middle', 0xC3: 'end',
         0xCC: 'stop_request', 0xCD: 'stop_receive'}


@dataclass(frozen=True)
class Header:
    type_byte: int
    sequence: int
    flags: int
    control: int
    command_byte_0: int
    command_byte_1: int
    declared_length: int
    code: int

    @classmethod
    def parse(cls, packet):
        if len(packet) < HEADER.size:
            raise ValueError('Truncated Creek header: require 11 bytes')
        return cls(*HEADER.unpack_from(packet))

    def to_bytes(self):
        try:
            return HEADER.pack(*asdict(self).values())
        except struct.error as exc:
            raise ValueError('Header field outside wire bounds') from exc

    def summary(self, packet_size):
        result = asdict(self)
        result.update(type_name=TYPES.get(self.type_byte, 'unknown'),
                      packet_size=packet_size, bytes_after_header=packet_size-HEADER.size,
                      length_semantics='unresolved', payload_omitted=True)
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('sample', type=Path, help='Raw packet, or virtual-peer JSONL with --events')
    p.add_argument('--events', action='store_true')
    a = p.parse_args()
    try:
        if a.sample.stat().st_size > 8*1024*1024:
            raise ValueError('Input exceeds inspection limit')
        if a.events:
            results = []
            for line in a.sample.read_text().splitlines():
                event = json.loads(line)
                if event.get('event') == 'gatt_write':
                    packet = bytes.fromhex(event['hex'])
                    results.append(Header.parse(packet).summary(len(packet)))
            print(json.dumps({'packets': results}, indent=2))
        else:
            packet = a.sample.read_bytes()
            print(json.dumps(Header.parse(packet).summary(len(packet)), indent=2))
        return 0
    except (OSError, ValueError, KeyError):
        print(json.dumps({'error': 'Invalid or truncated input; payload values omitted'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
