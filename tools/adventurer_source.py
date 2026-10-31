"""Prepare reviewed revision3/4 sources: digital time and original compass bindings.

Copies a bounded original source tree; never edits the original or transmits.
Raster resources are patched deterministically at declared component bounds.
No user photo is modified. All other source/resource pixels remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from .adventurer_digital import transform
from .sdk_compile_reference import validate_source

NORMAL_BOXES=((126,176,174,216),(294,176,342,216))
GAUGE_BOXES=((84,158,118,308),(348,158,382,308))
PATCH_PATHS={'bg_0888.bmp':'bg_0888.bmp',
             'Fade_bg_0_0565.bmp':'Fade/bg/Fade_bg_0_0565.bmp',
             'Fade_bg_1_0565.bmp':'Fade/bg/Fade_bg_1_0565.bmp'}


def clean_meter_background(image,name):
    if image.size!=(466,466) or name not in PATCH_PATHS:raise ValueError('Unknown target background')
    source=image.convert('RGB');out=source.copy()
    if name=='bg_0888.bmp':
        # The plain central gradient is nearly symmetric vertically. Copy its
        # matching lower patch, correcting the <=3/255 border gradient difference
        # from untouched left/right boundaries. No other pixels are changed.
        for left,top,right,bottom in NORMAL_BOXES:
            for y in range(top,bottom):
                mirror=465-y
                a=source.getpixel((left-1,y));am=source.getpixel((left-1,mirror))
                b=source.getpixel((right,y));bm=source.getpixel((right,mirror))
                for x in range(left,right):
                    weight=(x-left+1)/(right-left+1);base=source.getpixel((x,mirror))
                    pixel=tuple(max(0,min(255,round(base[c]+(1-weight)*(a[c]-am[c])+weight*(b[c]-bm[c])))) for c in range(3))
                    out.putpixel((x,y),pixel)
    else:
        # AOD has a solid black field; only the two baked gauge footprints change.
        for left,top,right,bottom in GAUGE_BOXES:
            out.paste((0,0,0),(left,top,right,bottom))
    return out


def revision4_images(source):
    """Deterministic resource edits; date month uses observed array/month schema."""
    from PIL import Image,ImageDraw,ImageEnhance
    firmware=Path(source)/'firmware';result={}
    for name,relative in PATCH_PATHS.items():
        with Image.open(firmware/relative) as image:
            out=clean_meter_background(image,name)
            # Remove baked heart in the AOD badge; normal heart is a sprite.
            if name!='bg_0888.bmp':out.paste((0,0,0),(211,287,255,329))
            result[relative]=out
    for relative in ('Hour_8888.png','Min_8888.png','Dot_8888.png'):
        with Image.open(firmware/relative) as image:
            out=image.convert('RGBA');alpha=out.getchannel('A')
            out=ImageEnhance.Brightness(out).enhance(0.24);out.putalpha(alpha)
            result[relative]=out
    for index,color in ((0,(176,205,83,180)),(1,(246,127,49,180))):
        # Preserve original 32x288 geometry and pivot (16,233). Only the
        # outermost 11px segment remains; native second pointer rotates it.
        out=Image.new('RGBA',(32,288));draw=ImageDraw.Draw(out)
        draw.line((16,8,16,19),fill=color,width=2)
        result[f'second/second_{index}_8888.png']=out
    separator=Image.new('RGBA',(8,20));ImageDraw.Draw(separator).ellipse((2,15,4,17),fill=(200,200,200,255))
    result['HeartRate_8888.png']=separator
    for month in range(1,13):
        out=Image.new('RGBA',(36,20))
        for position,digit in enumerate(f'{month:02d}'):
            with Image.open(firmware/f'Data/Data_{digit}_8888.png') as image:
                out.alpha_composite(image.convert('RGBA'),(18*position,0))
        result[f'Month/Month_{month-1}_8888.png']=out
    return result


def prepare_source(source,destination,revision=3):
    from PIL import Image
    source,model=validate_source(source)
    if model.get('platform')!='ats3089C':raise ValueError('Only actual ADVENTURER source supported')
    paths=list(source.rglob('*'))
    if len(paths)>1024 or sum(p.stat().st_size for p in paths if p.is_file())>32*1024*1024:
        raise ValueError('Source tree exceeds bounds')
    if destination.exists() or destination.is_symlink():raise FileExistsError('Destination must be new')
    edited,changes=transform(model,standalone=True,revision=revision)
    shutil.copytree(source,destination)
    (destination/'firmware/dial.json').write_text(json.dumps(edited,indent=2)+'\n')
    patches=[]
    for name,relative in PATCH_PATHS.items():
        original=source/'firmware'/relative;output=destination/'firmware'/relative
        with Image.open(original) as image:
            before=image.convert('RGB');after=clean_meter_background(before,name)
            after.save(output,format='BMP')
            patches.append({'resource':name,'original_pixels_sha256':hashlib.sha256(before.tobytes()).hexdigest(),
                            'new_pixels_sha256':hashlib.sha256(after.tobytes()).hexdigest(),
                            'original_file_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
                            'new_file_sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
    if revision==4:
        for relative,image in revision4_images(source).items():
            output=destination/'firmware'/relative;output.parent.mkdir(parents=True,exist_ok=True)
            image.save(output)
        patches.append({'revision4':'dimmed hands, rim second pointer, date separator and twelve numeric month images'})
    return {'revision':revision,'source_name':model['name'],'candidate_name':edited['name'],
            'changes':changes,'patched_images':patches,'physical_upload_attempted':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path)
    p.add_argument('--destination',required=True,type=Path);p.add_argument('--revision',type=int,choices=[3,4],default=3);a=p.parse_args()
    try:print(json.dumps(prepare_source(a.source,a.destination,a.revision),indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error_type':type(exc).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())
