"""Create a signed, bounded .hface package for the local Android installer."""
import argparse,hashlib,json,os,zipfile
from pathlib import Path
from .creek_bin import parse,read_binary

DOMAIN=b'HAMMER-FACE-PACKAGE-v1\0'


def create_package(binary,key_path,destination,title,origin_filename):
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import padding,rsa
    data=read_binary(binary);report=parse(data)
    if len(data)>1048576 or report['compression_marker']!=4:raise ValueError('Unsupported bounded face container')
    if report['name'].startswith(('ewr24dig','ewrcompass_24d')):raise ValueError('Unstable ADVENTURER test variants cannot be packaged')
    if not origin_filename.endswith('.bin') or report['name']+'.bin'==origin_filename:raise ValueError('Separate original/candidate filenames required')
    if not title or len(title)>100:raise ValueError('Invalid title')
    model=next(e['json'] for e in report['resources'] if e['name']=='dial.json')
    if model['name']!=report['name'] or model['resolution_ratio']!='466x466':raise ValueError('Unexpected layout identity or dimensions')
    if destination.exists() or destination.is_symlink():raise FileExistsError('Package destination must be new')
    if key_path.is_symlink() or key_path.stat().st_mode&0o077:raise ValueError('Private signing key requires mode 600')
    key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
    if not isinstance(key,rsa.RSAPrivateKey) or key.key_size!=2048:raise ValueError('Expected RSA2048 signing key')
    manifest={'schema':1,'title':title,'filename':report['name']+'.bin','origin_filename':origin_filename,
              'sha256':report['sha256'],'device_model':2039,'firmware':'2.0.12','platform':3,'color':72,
              'framework':8,'compression':4,'runtime_status':'Experimental — appearance and compass not yet verified on a watch'}
    metadata=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    signature=key.sign(DOMAIN+len(metadata).to_bytes(4,'big')+metadata+data,padding.PKCS1v15(),hashes.SHA256())
    with destination.open('xb') as out:
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED) as z:
            for name,value in [('manifest.json',metadata),('face.bin',data),('signature.bin',signature)]:
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.external_attr=0o100600<<16;z.writestr(info,value)
    return {'filename':destination.name,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
            'bytes':destination.stat().st_size,'face_sha256':report['sha256'],'signed':True,'runtime_status':manifest['runtime_status']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--key',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--title',required=True);p.add_argument('--origin-filename',required=True);a=p.parse_args()
    try:print(json.dumps(create_package(a.binary,a.key,a.destination,a.title,a.origin_filename),indent=2));return 0
    except (OSError,ValueError,KeyError):print(json.dumps({'error':'Invalid package input, signing key or destination'}));return 2


if __name__=='__main__':raise SystemExit(main())
