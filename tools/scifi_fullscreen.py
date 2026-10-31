"""Offline full-display Sci-Fi derivative: scaled native widgets, no outer frames."""
import argparse,copy,json,math,shutil
from pathlib import Path
from .sdk_compile_reference import validate_source

NAME='CWR05G_compassPL02'
SCALE=1.14
CENTER=233


def coordinate(n):return round(CENTER+(n-CENTER)*SCALE)
def dimension(n):return max(1,round(n*SCALE))


def transform(model):
    if model.get('name')!='CWR05G_compassPL01' or model.get('platform')!='ats3085s' or model.get('resolution_ratio')!='466x466':raise ValueError('Unexpected clean Sci-Fi base')
    out=copy.deepcopy(model);out['name']=NAME
    for layer in ('item','fade_item'):
        for widget in out[layer]:
            if widget.get('type')=='background':continue
            for key in ('x','y'):
                if key in widget:widget[key]=coordinate(widget[key])
            for key in ('w','h','centerx','centery'):
                if key in widget:widget[key]=dimension(widget[key])
            # Bitmap glyph rounding must not clip a full fixed-width time.
            if widget.get('type')=='time':widget['w']=4*dimension(56)+dimension(22)
            if widget.get('type')=='second' and widget.get('widget')=='text':widget['w']=2*dimension(25)
    return out


def background(image,model,firmware):
    from PIL import Image,ImageDraw
    if image.size!=(466,466):raise ValueError('Unexpected background size')
    source=image.convert('RGB');out=Image.new('RGB',(466,466))
    # Uniform LCD paper with a slight vertical tone change, without the old
    # raised outlines or diagonal frame. Native readout sprites remain separate.
    for y in range(466):
        t=y/465;color=tuple(round((1-t)*a+t*b) for a,b in zip((188,132,73),(180,123,64)))
        out.paste(color,(0,y,466,y+1))
    spans={}
    for y in range(466):
        xs=[x for x in range(466) if (lambda c:c[0]>c[1]+20 and c[1]>c[2]+15)(source.getpixel((x,y)))]
        if xs:spans[y]=(min(xs),max(xs)+1)
    if len(spans)<200:raise ValueError('Original orange LCD interior not found')
    # Retain the actual factory's useful baked labels and activity pictograms.
    # Orange row spans prevent the old outside black area becoming false ink.
    ink_regions=((94,84,174,110),(82,126,126,146),(166,126,225,146),
                 (104,344,132,372),(118,380,142,406),(241,344,270,373),(239,378,269,406))
    for left,top,right,bottom in ink_regions:
        patch=Image.new('RGBA',(right-left,bottom-top))
        for y in range(top,bottom):
            bounds=spans.get(y)
            if not bounds:continue
            for x in range(left,right):
                if not bounds[0]<=x<bounds[1]:continue
                red=source.getpixel((x,y))[0];alpha=max(0,min(255,round((184-red)*255/184)))
                if alpha:patch.putpixel((x-left,y-top),(0,0,0,alpha))
        patch=patch.resize((dimension(patch.width),dimension(patch.height)),Image.Resampling.LANCZOS)
        out.paste(patch,(coordinate(left),coordinate(top)),patch)
    draw=ImageDraw.Draw(out)
    for y in (176,225,331):draw.line((0,coordinate(y),465,coordinate(y)),fill='black',width=2)
    draw.line((0,coordinate(120),coordinate(249),coordinate(120)),fill='black',width=2)
    draw.line((coordinate(153),coordinate(120),coordinate(153),coordinate(151)),fill='black',width=2)
    draw.line((coordinate(139),coordinate(176),coordinate(139),coordinate(225)),fill='black',width=2)
    # Rebuild faint LCD segment guides from the same resized bitmap fonts so
    # their placement follows the enlarged native text exactly.
    ghosts={'time':'88:88','second':'88','step':'88888','calorie':'8888','sleep':'88H88','distance':'88.88'}
    for widget in model['item']:
        if widget.get('widget')!='text' or widget.get('type') not in ghosts:continue
        glyphs=[];font=widget['font']
        for char in ghosts[widget['type']]:
            index=10 if char in ':.' else 12 if char=='H' else 8
            with Image.open(Path(firmware)/font/f'{font}_{index}_8888.png') as im:
                glyph=im.convert('RGBA');alpha=glyph.getchannel('A').point(lambda a:round(a*.12));glyph=Image.new('RGBA',glyph.size);glyph.putalpha(alpha);glyphs.append(glyph)
        width=sum(g.width for g in glyphs)
        if width>widget['w']:raise ValueError('LCD guides exceed native text bounds')
        x,y=widget['x'],widget['y'];align=widget.get('align','left')
        if align=='right':x+=widget['w']-width
        elif align=='center':x+=(widget['w']-width)//2
        for glyph in glyphs:out.paste(glyph,(x,y),glyph);x+=glyph.width
    cx,cy=coordinate(341),coordinate(135);radius=dimension(50)
    ImageDraw.Draw(out).ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill='black')
    return out


def prepare(source,destination):
    from PIL import Image
    source,model=validate_source(source);destination=Path(destination).absolute()
    root=Path(__file__).resolve().parents[1]
    if not destination.resolve().is_relative_to(root/'faces/local'):raise ValueError('Vendor resources must remain in ignored faces/local')
    if destination.exists() or destination.is_symlink():raise FileExistsError('New destination required')
    paths=list(source.rglob('*'))
    if len(paths)>1024 or sum(p.stat().st_size for p in paths if p.is_file())>32*1024*1024:raise ValueError('Source exceeds bounds')
    edited=transform(model);shutil.copytree(source,destination);firmware=destination/'firmware';changed=[]
    for path in (source/'firmware').rglob('*'):
        if not path.is_file() or path.suffix.lower() not in {'.png','.bmp'}:continue
        relative=path.relative_to(source/'firmware');target=firmware/relative
        if path.name in {'preview_0565.bmp','app_preview.png','background_0_0565.bmp'}:continue
        with Image.open(path) as image:
            out=image.resize((dimension(image.width),dimension(image.height)),Image.Resampling.LANCZOS)
            out.save(target);changed.append({'resource':path.name,'from':list(image.size),'to':list(out.size)})
    with Image.open(source/'firmware/background_0_0565.bmp') as original:
        background(original,edited,firmware).save(firmware/'background_0_0565.bmp')
    changed.append({'resource':'background_0_0565.bmp','from':[466,466],'to':[466,466]})
    (firmware/'dial.json').write_text(json.dumps(edited,indent=2)+'\n')
    rectangles=[]
    for layer in ('item','fade_item'):
        for widget in edited[layer]:
            if widget.get('widget') not in {'text','array'}:continue
            x,y,w,h=(widget[k] for k in ('x','y','w','h'))
            radius=max(math.hypot(px-CENTER,py-CENTER) for px in (x,x+w-1) for py in (y,y+h-1))
            if radius>232:raise ValueError('Readout would reach round-screen clip boundary')
            rectangles.append({'layer':layer,'type':widget['type'],'outermost_corner_radius':round(radius,3)})
    return {'name':NAME,'base_name':model['name'],'scale':SCALE,'display':[466,466],
            'background':'Orange to the round screen edge; grey outer frames removed; native compass retains dark disk',
            'changed_images':changed,'readout_bounds':rectangles,'native_bindings_changed':False,
            'physical_upload_attempted':False,'rendering':'Offline static preview is not watch-firmware validation'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(prepare(a.source,a.destination),indent=2));return 0
    except (OSError,ValueError,KeyError):print('{"error":"Invalid full-display source or bounds; no device access"}');return 2


if __name__=='__main__':raise SystemExit(main())
