"""Offline ADVENTURER candidate: edit only layout JSON; never install or transmit."""
import argparse
import copy
import json
from pathlib import Path
from .creek_bin import parse,read_binary,replace_json

TARGET='ewrcompass_0819@LC'
TEST_NAME='ewr24digital'
TEST_NAMES={1:TEST_NAME,2:'ewr24dig02',3:'ewr24dig03',4:'ewr24dig04',5:'ewr24dig05',6:'ewr24dig06',7:'ewrcompass_24d07@LC'}
METER_TYPES={'air_pressure','altitude','altitude_min','altitude_max','altitude_unit'}
METER_PICTURES={'Unit_2_8888.png','air_0_8888.png','air_1_8888.png','PA1_8888.png','PB1_8888.png','PA2_8888.png','PB2_8888.png'}
CLOCK_TYPES={'hour','min','second'}


def format_hhmm(hour,minute):
    """Preview/test formatter; firmware rendering still needs hardware acceptance."""
    if type(hour) is not int or type(minute) is not int or not 0<=hour<24 or not 0<=minute<60:
        raise ValueError('Invalid 24-hour time')
    return f'{hour:02d}:{minute:02d}'


def transform(model,palette_index=None,standalone=False,revision=1):
    if type(revision) is not int or revision not in TEST_NAMES:raise ValueError('Unknown layout revision')
    if (model.get('name')!=TARGET or model.get('platform')!='ats3089C'
            or model.get('resolution_ratio')!='466x466'):
        raise ValueError('Only the acquired ADVENTURER 466x466 source is supported')
    if palette_index is not None and (type(palette_index) is not int or palette_index not in (0,1)):
        raise ValueError('Palette index must be 0 or 1')
    out=copy.deepcopy(model);removed={};removed_meters={};moved=[]
    for layer in ('item','fade_item'):
        items=out.get(layer)
        if not isinstance(items,list):raise ValueError('Missing ADVENTURER layers')
        clocks=[x for x in items if x.get('widget')=='pointer' and x.get('type') in CLOCK_TYPES]
        if {x['type'] for x in clocks} != (CLOCK_TYPES if layer=='item' else {'hour','min'}):
            raise ValueError('Unexpected clock layout; refusing an ambiguous edit')
        kept=[];removed[layer]=[];removed_meters[layer]=[]
        for x in items:
            if (x.get('widget')=='pointer' and x.get('type') in CLOCK_TYPES) or x.get('picture')=='Dot_8888.png':
                removed[layer].append(x);continue
            if revision>=3 and (x.get('type') in METER_TYPES or x.get('picture') in METER_PICTURES):
                removed_meters[layer].append(x);continue
            if x.get('type')=='compass_hint':
                new_y=235 if revision>=3 else (203 if revision==2 else 120)
                moved.append({'layer':layer,'type':'compass_hint','old_y':x['y'],'new_y':new_y})
                x['y']=new_y # Calibration warning above the digital clock.
            kept.append(x)
        # Same bitmap time widget schema as a real SDK reference face. The
        # acquired ADVENTURER binary already includes all eleven Time glyphs.
        clock={'widget':'text','type':'time','x':97 if revision>=3 and layer=='item' else 145,'y':183 if revision>=3 else (140 if revision==2 else 174),'w':176,'h':40,
               'font':'Time','fontnum':11,'enable_font':0,'min_numwidth':2,
               'unit_count':10,'align':'center'}
        if layer=='fade_item':clock['color']='#2e2e2f'
        out[layer]=kept+[clock]
        if revision>=3 and layer=='item':
            out[layer]+=[{'widget':'icon','type':'other','x':273,'y':183,
                'w':16,'h':40,'picture':'Time_10_8888.png'},
                {'widget':'text','type':'second','x':289,'y':183,'w':80,'h':40,
                'font':'Time','fontnum':10,'enable_font':0,'min_numwidth':2,'align':'center'}]
        if revision==2 and layer=='item':
            # Diagnostic: observed text/second schema, using existing 26px glyphs.
            # This tests a redraw dependency; it does not prove the cause of freezing.
            out[layer].append({'widget':'text','type':'second','x':205,'y':253,
                'w':56,'h':26,'font':'Hr','fontnum':10,'enable_font':0,
                'min_numwidth':2,'align':'center'})
    if revision>=4:
        for layer in ('item','fade_item'):
            kept=[x for x in out[layer] if x.get('type')!='heart' and x.get('picture')!='HeartRate_8888.png']
            # Keep the factory pointer model and its serials/pivots. Render below
            # digital time; sprite changes are performed by the source builder.
            pointers=[copy.deepcopy(x) for x in model[layer] if
                      (x.get('widget')=='pointer' and x.get('type') in CLOCK_TYPES)
                      or x.get('picture')=='Dot_8888.png']
            index=next(i for i,x in enumerate(kept) if x.get('type')=='time')
            kept[index:index]=pointers
            date=[{'widget':'text','type':'day','x':193,'y':325,'w':36,'h':20,
                   'font':'Data','fontnum':10,'enable_font':0,'min_numwidth':2,'align':'center'},
                  {'widget':'icon','type':'other','x':229,'y':325,'w':8,'h':20,'picture':'HeartRate_8888.png'},
                  {'widget':'array','type':'month','x':237,'y':325,'w':36,'h':20,
                   'count':12,'array_img':'Month','enable_font':0,'min_numwidth':2,'align':'center'}]
            if layer=='fade_item':
                for x in date:x['color']='#2e2e2f'
            out[layer]=kept+date
    if revision>=5:
        for layer in ('item','fade_item'):
            items=[x for x in out[layer] if x.get('type') not in {'day','month'} and x.get('picture')!='HeartRate_8888.png']
            clock=next(x for x in items if x.get('type')=='time')
            clock.update(x=69 if layer=='item' else 127,y=175,w=212,h=58)
            if layer=='item':
                colon=next(x for x in items if x.get('picture')=='Time_10_8888.png')
                colon.update(x=281,y=175,w=20,h=58)
                seconds=next(x for x in items if x.get('type')=='second' and x.get('widget')=='text')
                seconds.update(x=301,y=175,w=96,h=58)
                # Exact known sensor widget types from acquired weather source.
                items.extend([
                    {'widget':'icon','type':'compass_icon','x':229,'y':251,'w':8,'h':12,
                     'enable_hidden':1,'picture':'WAngle_8888.png','color':'#F67F31'},
                    {'widget':'text','type':'angle','x':201,'y':270,'w':64,'h':28,
                     'fontnum':12,'font':'WData','unit_count':11,'unit_ext':10,
                     'enable_font':0,'align':'center','color':'#F67F31'}])
            items.extend([
                {'widget':'array','type':'week','x':0,'y':0,'w':466,'h':466,
                 'count':7,'array_img':'WWeek','color':'#F67F31'},
                {'widget':'curved','type':'day','x':223,'y':95,'w':466,'h':466,
                 'centerx':10,'centery':138,'angle':166,'angle_space':-10,'total_count':2,
                 'fontnum':10,'font':'WDay','min_numwidth':2,'color':'#F67F31'}])
            out[layer]=items
    if revision==7:
        for layer in ('item','fade_item'):
            for item in out[layer]:
                if item.get('type')=='time':item.update(x=72 if layer=='item' else 129,y=176,w=208,h=57)
                if item.get('picture')=='Time_10_8888.png':item.update(x=280,y=176,w=20,h=57)
                if item.get('widget')=='text' and item.get('type')=='second':item.update(x=300,y=176,w=94,h=57)
    if palette_index is not None:
        out['cur_sn']=palette_index
        for layer in ('item','fade_item'):
            for x in out[layer]:
                if 'cur_sn' in x:x['cur_sn']=palette_index
                colors=x.get('sn_color_list')
                if colors:
                    if len(colors)!=2:raise ValueError('Unexpected palette count')
                    x['color']=colors[palette_index]
    if standalone:out['name']=TEST_NAMES[revision]
    return out,{'removed_clock_items':{k:len(v) for k,v in removed.items()},
                'removed_meter_items':{k:len(v) for k,v in removed_meters.items()},
                'moved_warning':moved,'palette_index':palette_index,'standalone':standalone,'revision':revision,
                'second_tick_probe':revision>=2,'meters_removed':revision>=3,
                'time_format':'Uses firmware time widget and watch 24-hour preference; runtime untested',
                'preview_staleness':'Original analog preview images intentionally preserved; not a rendered proof'}


def build(data,palette_index=None,standalone=False,revision=1):
    if revision>=3:raise ValueError('Revision3 changes image resources; prepare its source tree with tools.adventurer_source and use the SDK compiler')
    source=parse(data)
    if source['name']!=TARGET:raise ValueError('Not the acquired ADVENTURER container')
    resources=source['resources']
    expected={f'Time_{i}_8888.png' for i in range(11)}
    if not expected.issubset({r['name'] for r in resources}):
        raise ValueError('Digital glyph resources are missing')
    docs=[r for r in resources if r['name']=='dial.json' and 'json' in r]
    if len(docs)!=1:raise ValueError('Expected one parsed dial.json')
    model,changes=transform(docs[0]['json'],palette_index,standalone,revision)
    replacement=json.dumps(model,separators=(',',':'),ensure_ascii=False).encode()
    result=replace_json(data,'dial.json',replacement)
    if standalone:
        name=TEST_NAMES[revision].encode();result=name+bytes(30-len(name))+result[30:]
    after=parse(result)
    before_assets=[(r['name'],r['sha256']) for r in resources if r['name']!='dial.json']
    after_assets=[(r['name'],r['sha256']) for r in after['resources'] if r['name']!='dial.json']
    if before_assets!=after_assets:raise ValueError('Non-layout resource changed')
    return result,model,{'source_sha256':source['sha256'],'candidate_sha256':after['sha256'],
        'candidate_name':after['name'],'bytes':len(result),'crc_valid':after['crc_valid'],'unchanged_asset_count':len(before_assets),
        'changes':changes,'installation_tested':False,'complications_runtime_tested':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('--destination',required=True,type=Path)
    p.add_argument('--palette-index',type=int,choices=[0,1])
    p.add_argument('--revision',type=int,choices=[1,2],default=1,help='2: corrected clock position plus diagnostic normal-mode seconds widget')
    p.add_argument('--standalone',action='store_true',help='Use dedicated ewr24digital name in JSON and header, preserving factory face')
    a=p.parse_args()
    try:
        result,model,report=build(read_binary(a.source),a.palette_index,a.standalone,a.revision)
        if a.destination.exists() or a.destination.is_symlink():raise FileExistsError('Destination must be new')
        # A new explicit directory keeps candidate, IR and checks together.
        a.destination.mkdir()
        (a.destination/'candidate.bin').write_bytes(result)
        (a.destination/'dial.json').write_text(json.dumps(model,indent=2)+'\n')
        (a.destination/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error_type':type(exc).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())
