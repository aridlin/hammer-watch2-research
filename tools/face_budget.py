"""Offline decoded image-storage budget; never estimates actual peak firmware RAM."""
import argparse,json,struct
from pathlib import Path
from .creek_bin import parse,read_binary


def image_budget(data):
    report=parse(data);images=[];unknown=[]
    for item in report['resources']:
        if not item['name'].lower().endswith(('.bmp','.png')):continue
        raw=data[item['offset']:item['offset']+item['size']]
        if len(raw)<4:unknown.append(item['name']);continue
        word=struct.unpack_from('<I',raw)[0];fmt=word&31
        width=(word>>10)&2047;height=(word>>21)&2047
        if word&0x3e0 or fmt not in {4,12,24} or not width or not height:
            unknown.append(item['name']);continue
        images.append({'name':item['name'],'width':width,'height':height,'format_marker':fmt,
                       'stored_bytes':item['size'],'decoded_pixel_bytes':width*height*{4:2,12:3,24:4}[fmt]})
    return {'sha256':report['sha256'],'container_bytes':len(data),'image_count':len(images),
            'decoded_image_bytes_sum':sum(x['decoded_pixel_bytes'] for x in images),
            'largest_images':sorted(images,key=lambda x:x['decoded_pixel_bytes'],reverse=True)[:16],
            'weekday_images':[x for x in images if x['name'].startswith(('week_','WWeek_'))],
            'unknown_image_headers':unknown,
            'limitation':'Sum of image pixel storage is NOT peak RAM. Decoder caching, widget invalidation, sensor scheduling and firmware crash cause are unknown.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);a=p.parse_args()
    try:print(json.dumps(image_budget(read_binary(a.source)),indent=2));return 0
    except (OSError,ValueError):print(json.dumps({'error':'Invalid or unsupported binary'}));return 2


if __name__=='__main__':raise SystemExit(main())
