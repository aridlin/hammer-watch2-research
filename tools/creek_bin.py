"""Observed Creek SDK 10.7 BIN container. Offline only; target firmware unverified."""
import argparse
import base64
import hashlib
import json
from pathlib import Path,PurePosixPath
import struct
import sys
import zlib

HEADER=44
ENTRY=38
MAGIC=0x5AA54321
LIMIT=64*1024*1024


def read_binary(path):
    p=Path(path)
    if p.stat().st_size>LIMIT:raise ValueError('BIN exceeds 64 MiB limit')
    data=p.read_bytes()
    if len(data)>LIMIT:raise ValueError('BIN exceeds limit')
    return data


def parse(data,verify_crc=True):
    if len(data)<HEADER or len(data)>LIMIT:raise ValueError('Truncated or oversized BIN')
    magic=struct.unpack_from('<I',data,30)[0]
    if magic!=MAGIC:raise ValueError('Not the observed Creek container magic')
    count=struct.unpack_from('<H',data,37)[0]
    if count>4096:raise ValueError('Resource count exceeds limit')
    index_end=HEADER+count*ENTRY
    if index_end>len(data):raise ValueError('Truncated resource index')
    stored=struct.unpack_from('<I',data,40)[0];actual=zlib.crc32(data[HEADER:])
    if verify_crc and stored!=actual:raise ValueError('Container CRC32 mismatch')
    entries=[]
    for i in range(count):
        raw_name,offset,size=struct.unpack_from('<30sII',data,HEADER+i*ENTRY)
        if offset<index_end or offset+size>len(data):raise ValueError('Resource outside container payload')
        raw=data[offset:offset+size]
        item={'index':i,'name':raw_name.split(b'\0',1)[0].decode('utf-8',errors='replace'),
              'name_raw_hex':raw_name.hex(),'offset':offset,'size':size,
              'sha256':hashlib.sha256(raw).hexdigest()}
        if item['name'].endswith('.json'):
            try:item['json']=json.loads(raw)
            except (ValueError,UnicodeError):item['json_status']='not_decodable'
        entries.append(item)
    occupied=sorted((e['offset'],e['offset']+e['size']) for e in entries if e['size'])
    for a,b in zip(occupied,occupied[1:]):
        if b[0]<a[1]:raise ValueError('Overlapping resource ranges are unsupported')
    return {'schema_version':1,'kind':'creek_sdk_bin','target_compatibility':'unverified',
            'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),
            'name':data[:30].split(b'\0',1)[0].decode('utf-8',errors='replace'),
            'magic_hex':f'{magic:08x}','dial_type':data[34],
            'dial_version':struct.unpack_from('<H',data,35)[0],
            'resource_count':count,'compression_marker':data[39],
            'stored_crc32':f'{stored:08x}','calculated_crc32':f'{actual:08x}',
            'crc_valid':stored==actual,'index_end':index_end,'resources':entries}


def export_ir(data):
    report=parse(data)
    boundary=report['index_end']
    segments=[];cursor=boundary
    for item in sorted(report['resources'],key=lambda e:e['offset']):
        if item['offset']>cursor:
            segments.append({'kind':'gap','offset':cursor,'data_base64':base64.b64encode(data[cursor:item['offset']]).decode()})
            cursor=item['offset']
        if item['size']:
            end=item['offset']+item['size']
            segments.append({'kind':'resource','index':item['index'],'offset':cursor,
                'data_base64':base64.b64encode(data[cursor:end]).decode()})
            cursor=end
    if cursor<len(data):
        segments.append({'kind':'trailing','offset':cursor,'data_base64':base64.b64encode(data[cursor:]).decode()})
    return {'schema_version':1,'kind':'creek_bin_lossless_ir','source_sha256':report['sha256'],
            'inspection':report,'header_base64':base64.b64encode(data[:HEADER]).decode(),
            'index_base64':base64.b64encode(data[HEADER:boundary]).decode(),'segments':segments}


def rebuild(ir):
    if ir.get('schema_version')!=1 or ir.get('kind')!='creek_bin_lossless_ir':raise ValueError('Unsupported IR')
    decode=lambda value:base64.b64decode(value,validate=True)
    header=decode(ir['header_base64']);index=decode(ir['index_base64'])
    if len(header)!=HEADER:raise ValueError('Invalid header length')
    count=struct.unpack_from('<H',header,37)[0]
    if count>4096 or len(index)!=count*ENTRY:raise ValueError('Invalid index length')
    out=bytearray(header+index)
    for segment in ir['segments']:
        if segment['offset']!=len(out):raise ValueError('IR segments must be contiguous and ordered')
        raw=decode(segment['data_base64'])
        if len(out)+len(raw)>LIMIT:raise ValueError('IR exceeds size limit')
        out.extend(raw)
    result=bytes(out)
    parse(result)
    if hashlib.sha256(result).hexdigest()!=ir['source_sha256']:
        raise ValueError('Lossless rebuild differs from source; use explicit JSON replacement for edits')
    return result


def replace_json(data,name,replacement):
    report=parse(data)
    matches=[e for e in report['resources'] if e['name']==name]
    if len(matches)!=1 or not name.endswith('.json'):raise ValueError('Select exactly one JSON resource')
    if not isinstance(json.loads(replacement),dict):raise ValueError('Replacement JSON must be an object')
    item=matches[0];start=item['offset'];end=start+item['size'];delta=len(replacement)-item['size']
    if len(data)+delta>LIMIT:raise ValueError('Replacement exceeds size limit')
    out=bytearray(data[:start]+replacement+data[end:])
    for entry in report['resources']:
        record=HEADER+entry['index']*ENTRY
        if entry['index']==item['index']:
            struct.pack_into('<I',out,record+34,len(replacement))
        elif entry['offset']>=end:
            struct.pack_into('<I',out,record+30,entry['offset']+delta)
    struct.pack_into('<I',out,40,zlib.crc32(out[HEADER:]))
    parse(out)
    return bytes(out)


def extract(data,destination):
    import shutil,tempfile
    report=parse(data);dest=Path(destination).absolute()
    if dest.exists() or dest.is_symlink():raise FileExistsError('Destination must be new')
    if not dest.parent.is_dir():raise ValueError('Destination parent must exist')
    names=set()
    for e in report['resources']:
        name=e['name'];p=PurePosixPath(name)
        if not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts:
            raise ValueError('Unsafe resource name')
        if str(p).casefold() in names:raise ValueError('Duplicate resource name')
        names.add(str(p).casefold())
    temporary=Path(tempfile.mkdtemp(prefix='.creek-bin-',dir=dest.parent))
    try:
        for e in report['resources']:
            out=temporary/e['name'];out.parent.mkdir(parents=True,exist_ok=True)
            out.write_bytes(data[e['offset']:e['offset']+e['size']])
        dest.mkdir()
        try:
            for child in temporary.iterdir():shutil.move(str(child),dest/child.name)
        except Exception:shutil.rmtree(dest);raise
    finally:shutil.rmtree(temporary)
    return {'destination':str(dest),'resources':len(report['resources'])}



def decode_image(data, name):
    from PIL import Image
    import lz4.block
    report=parse(data)
    if report['compression_marker']!=4:raise ValueError('Only observed compression marker 4 is supported')
    matches=[e for e in report['resources'] if e['name']==name]
    if len(matches)!=1:raise ValueError('Select one image resource')
    e=matches[0];raw=data[e['offset']:e['offset']+e['size']]
    if len(raw)<5:raise ValueError('Truncated image resource')
    word=struct.unpack_from('<I',raw)[0]
    fmt=word&31;width=(word>>10)&2047;height=(word>>21)&2047
    if word&0x3e0 or not width or not height:raise ValueError('Unsupported image header')
    if fmt not in (4,12,24):raise ValueError('Unobserved image format marker')
    size=width*height*({4:2,12:3,24:4}[fmt])
    try:
        pixels=lz4.block.decompress(raw[4:],uncompressed_size=size)
    except lz4.block.LZ4BlockError:
        raise ValueError('Invalid LZ4 image payload') from None
    if len(pixels)!=size:raise ValueError('Image size mismatch')
    return Image.frombytes('RGBA' if fmt==24 else 'RGB',(width,height),pixels,'raw',{4:'BGR;16',12:'BGR',24:'BGRA'}[fmt])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    for command in ['inspect','export-ir','extract']:
        q=sub.add_parser(command);q.add_argument('file')
        q.add_argument('--output' if command!='extract' else '--destination',required=True,type=Path)
    q=sub.add_parser('decode-image');q.add_argument('file');q.add_argument('--name',required=True);q.add_argument('--destination',required=True,type=Path)
    q=sub.add_parser('rebuild');q.add_argument('file');q.add_argument('--destination',required=True,type=Path)
    q=sub.add_parser('replace-json');q.add_argument('file');q.add_argument('--name',required=True)
    q.add_argument('--replacement',required=True);q.add_argument('--destination',required=True,type=Path)
    a=p.parse_args()
    try:
        target=getattr(a,'output',None) or getattr(a,'destination',None)
        if target.exists() or target.is_symlink():raise FileExistsError('Output must be new')
        if a.command=='decode-image':
            image=decode_image(read_binary(a.file),a.name)
            with target.open('xb') as f:image.save(f,format='PNG')
            return 0
        if a.command=='rebuild':
            ir_path=Path(a.file)
            if ir_path.stat().st_size>128*1024*1024:raise ValueError('IR exceeds limit')
            result=rebuild(json.loads(ir_path.read_text()))
        else:
            data=read_binary(a.file)
            if a.command=='extract':result=extract(data,a.destination)
            elif a.command=='inspect':result=parse(data)
            elif a.command=='export-ir':result=export_ir(data)
            else:result=replace_json(data,a.name,read_binary(a.replacement))
        if isinstance(result,bytes):
            with target.open('xb') as f:f.write(result)
        elif a.command!='extract':
            with target.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
        else:print(json.dumps(result))
        return 0
    except (ValueError,OSError,KeyError,TypeError,struct.error,ImportError,RuntimeError) as exc:
        print(json.dumps({'error_type':type(exc).__name__,'message':str(exc)}),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
