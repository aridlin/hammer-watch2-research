"""Prepare the acquired Sci-Fi Timer orange/Polish/native-compass edit offline."""
import argparse,copy,hashlib,json,shutil
from pathlib import Path
from .sdk_compile_reference import validate_source

NAME='CWR05G_compassPL01'
LABELS=('pon','wt','śr','czw','pt','sob','ndz')
TEXT_MASKS={'explore':(145,24,320,55),'be_proactive':(74,152,220,173),
            'collaborate':(0,145,35,322),'innovate':(434,145,466,299),
            'sport_and_arrows':(124,423,342,466)}
CLOCK_ELLIPSE=(263,57,419,213)


def transform(model,weather):
    if model.get('name')!='CWR05G_23612' or model.get('platform')!='ats3085s' or model.get('resolution_ratio')!='466x466':raise ValueError('Unexpected Sci-Fi source')
    if weather.get('name')!='ewr01_compass_4':raise ValueError('Unexpected weather source')
    out=copy.deepcopy(model);out['name']=NAME
    removed=[x for x in out['item'] if x.get('widget')=='pointer' and x.get('type') in {'hour','min','second'} or x.get('picture')=='icon1_8888.png']
    if len(removed)!=4:raise ValueError('Unexpected corner clock schema')
    out['item']=[x for x in out['item'] if x not in removed]
    compass=[]
    for widget in weather['item']:
        selected=(widget.get('picture')=='ring_8888.png' and widget.get('x')==185) or widget.get('picture') in {'scal_8888.png','angle_8888.png'} or widget.get('type') in {'angle','compass_pos','compass_hint'}
        if not selected:continue
        w=copy.deepcopy(widget);w['x']+=108;w['y']-=219
        for key in ('cur_sn','sn_count','sn_list','sn_color_list','sn_type'):w.pop(key,None)
        w['color']='#F67F31'
        if w.get('picture'):w['picture']='Compass_'+w['picture']
        if w.get('font'):w['font']='Compass_'+w['font']
        compass.append(w)
    if len(compass)!=6:raise ValueError('Weather compass component count differs')
    out['item']+=compass
    return out


def prepare(source,weather_source,destination):
    from PIL import Image,ImageDraw,ImageFont
    source=Path(source).resolve();weather_source=Path(weather_source).resolve();destination=Path(destination).absolute()
    source,model=validate_source(source)
    weather=json.loads((weather_source/'firmware/dial.json').read_bytes())
    if destination.exists() or destination.is_symlink():raise FileExistsError('New destination required')
    for tree in (source,weather_source):
        paths=list(tree.rglob('*'))
        if any(p.is_symlink() for p in paths) or len(paths)>1024 or sum(p.stat().st_size for p in paths if p.is_file())>32*1024*1024:raise ValueError('Unsafe/oversized source')
    edited=transform(model,weather);shutil.copytree(source,destination);firmware=destination/'firmware'
    orange=source/'app/color_picture/#B87F44/background_0_0565.bmp'
    with Image.open(orange) as im:
        image=im.convert('RGB');draw=ImageDraw.Draw(image)
        for l,t,r,b in TEXT_MASKS.values():draw.rectangle((l,t,r-1,b-1),fill='black')
        draw.ellipse(CLOCK_ELLIPSE,fill='black');image.save(firmware/'background_0_0565.bmp')
    font=ImageFont.truetype('DejaVuSansMono-BoldOblique.ttf',80)
    for i,label in enumerate(LABELS):
        box=font.getbbox(label);glyph=Image.new('RGBA',(box[2]-box[0],box[3]-box[1]))
        ImageDraw.Draw(glyph).text((-box[0],-box[1]),label,font=font,fill=(0,0,0,255))
        glyph.thumbnail((224,80),Image.Resampling.LANCZOS);canvas=Image.new('RGBA',(224,80))
        canvas.alpha_composite(glyph,((224-glyph.width)//2,(80-glyph.height)//2))
        canvas.resize((56,20),Image.Resampling.LANCZOS).save(firmware/f'Week/Week_{i}_8888.png')
    for name in ('ring_8888.png','scal_8888.png','angle_8888.png','Warning_8888.png'):
        shutil.copy2(weather_source/'firmware'/name,firmware/('Compass_'+name))
    for group,count in [('data',12),('direction',8)]:
        folder=firmware/('Compass_'+group);folder.mkdir()
        for i in range(count):shutil.copy2(weather_source/f'firmware/{group}/{group}_{i}_8888.png',folder/f'Compass_{group}_{i}_8888.png')
    (firmware/'dial.json').write_text(json.dumps(edited,indent=2)+'\n')
    config=destination/'app/app.json';app=json.loads(config.read_bytes());app['color']['current_color']='#B87F44';config.write_text(json.dumps(app,indent=2)+'\n')
    return {'source_name':model['name'],'candidate_name':NAME,'orange_source_sha256':hashlib.sha256(orange.read_bytes()).hexdigest(),
            'removed_text_masks':TEXT_MASKS,'removed_corner_clock_widgets':4,'added_native_weather_widgets':6,
            'weekday_dimensions':[56,20],'polish_weekdays':LABELS,'compass_runtime':'Unverified on hardware',
            'live_upload_attempted':False,'stability':'Unverified; source compilation is not runtime acceptance'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--weather-source',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(prepare(a.source,a.weather_source,a.destination),indent=2));return 0
    except (OSError,ValueError,KeyError):print(json.dumps({'error':'Unexpected source or destination; no device access'}));return 2


if __name__=='__main__':raise SystemExit(main())
