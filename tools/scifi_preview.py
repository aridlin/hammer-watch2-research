"""Compose a static layout preview from real compiled assets; not watch emulation."""
import argparse,json
from pathlib import Path
from .creek_bin import decode_image,read_binary,parse


def preview(data):
    from PIL import Image
    if parse(data)['name']=='CWR05G_compassPL02':return preview_fullscreen(data)
    if parse(data)['name']!='CWR05G_compassPL01':raise ValueError('Unexpected preview source')
    image=decode_image(data,'background_0_0565.bmp').convert('RGBA')
    def paste(name,x,y,tint=None):
        asset=decode_image(data,name).convert('RGBA')
        if tint:
            alpha=asset.getchannel('A');asset=Image.new('RGBA',asset.size,tint);asset.putalpha(alpha)
        image.alpha_composite(asset,(x,y))
    def digits(text,font,x,y,tint=None):
        for char in text:
            index=10 if char in ':.' else 12 if char=='H' else int(char)
            asset=decode_image(data,f'{font}_{index}_8888.png').convert('RGBA')
            if tint:
                alpha=asset.getchannel('A');asset=Image.new('RGBA',asset.size,tint);asset.putalpha(alpha)
            image.alpha_composite(asset,(x,y));x+=asset.width
    paste('icon2_8888.png',185,86);paste('Week_5_8888.png',60,193)
    digits('09:30','Time',68,238);digits('01','Second',348,243)
    digits('31','Date',160,193);paste('Date_10_8888.png',188,193);digits('10','Date',202,193)
    digits('5300','Data',147,348);digits('1866','Data',147,382);digits('44.2','Data',274,348);paste('Unit_0_8888.png',336,348);digits('07H30','Data',274,382)
    digits('100','Batteries',185,86)
    orange=(246,127,49,255)
    paste('Compass_ring_8888.png',293,87,orange);paste('Compass_scal_8888.png',293,87,orange)
    # Illustrative bearing only. Firmware rotation/render scheduling is unknown.
    arrow=Image.new('RGBA',(466,466));asset=decode_image(data,'Compass_angle_8888.png').convert('RGBA');alpha=asset.getchannel('A');asset=Image.new('RGBA',asset.size,orange);asset.putalpha(alpha);arrow.alpha_composite(asset,(337,88))
    arrow=arrow.rotate(-45,center=(341,135),resample=Image.Resampling.BICUBIC);image.alpha_composite(arrow)
    digits('045','Compass_data',309,115,orange);paste('Compass_data_11_8888.png',357,115,orange);paste('Compass_direction_1_8888.png',321,146,orange)
    return image.convert('RGB')


def preview_fullscreen(data):
    """Asset-based native-layout illustration, with fixed example values."""
    from PIL import Image,ImageDraw
    report=parse(data);model=next(r['json'] for r in report['resources'] if r['name']=='dial.json')
    image=decode_image(data,'background_0_0565.bmp').convert('RGBA');orange=(246,127,49,255)
    def asset(name,tint=None):
        im=decode_image(data,name).convert('RGBA')
        if tint:
            alpha=im.getchannel('A');im=Image.new('RGBA',im.size,tint);im.putalpha(alpha)
        return im
    samples={'time':'09:30','second':'01','day':'31','month':'10','step':'5300',
             'calorie':'1866','distance':'44.2','sleep':'07H30','battery':'100','angle':'045o'}
    ring=next(w for w in model['item'] if w.get('picture')=='Compass_ring_8888.png')
    cx=ring['x']+ring['w']//2;cy=ring['y']+ring['h']//2
    for widget in model['item']:
        kind=widget.get('widget');typ=widget.get('type');x=widget['x'];y=widget['y']
        if typ=='background' or typ=='compass_hint':continue
        if kind=='icon':
            picture=asset(widget['picture'],orange if widget['picture'].startswith('Compass_') else None)
            if typ=='compass_icon':
                layer=Image.new('RGBA',(466,466));layer.alpha_composite(picture,(x,y));image.alpha_composite(layer.rotate(-45,center=(cx,cy),resample=Image.Resampling.BICUBIC))
            else:image.alpha_composite(picture,(x,y))
        elif kind=='array' and typ in {'week','units'}:
            index=5 if typ=='week' else 0;image.alpha_composite(asset(f"{widget['array_img']}_{index}_8888.png"),(x,y))
        elif kind=='text':
            if typ=='compass_pos':glyphs=[asset('Compass_direction_1_8888.png',orange)]
            elif typ in samples:
                glyphs=[]
                for char in samples[typ]:
                    index=10 if char in ':.' else 12 if char=='H' else 11 if char=='o' else int(char)
                    glyphs.append(asset(f"{widget['font']}_{index}_8888.png",orange if typ=='angle' else None))
            else:continue
            width=sum(g.width for g in glyphs);align=widget.get('align','left')
            if align=='right':x+=widget['w']-width
            elif align=='center':x+=(widget['w']-width)//2
            for glyph in glyphs:image.alpha_composite(glyph,(x,y));x+=glyph.width
    # The physical panel is round; pixels outside this disk are not displayed.
    mask=Image.new('L',(466,466));ImageDraw.Draw(mask).ellipse((0,0,465,465),fill=255)
    result=Image.new('RGB',(466,466));result.paste(image.convert('RGB'),(0,0),mask)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('binary',type=Path);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    try:
        if a.destination.exists() or a.destination.is_symlink():raise FileExistsError('New destination required')
        image=preview(read_binary(a.binary));image.save(a.destination,format='PNG')
        print(json.dumps({'static_preview':True,'watch_firmware_emulated':False,'sensor_values':'Illustrative fixed samples'}));return 0
    except (OSError,ValueError):print('{"error":"Invalid preview input or destination"}');return 2


if __name__=='__main__':raise SystemExit(main())
