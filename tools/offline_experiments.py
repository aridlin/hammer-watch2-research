"""Build controlled local source packs; no radio, install or firmware API.

Vendor resources stay below faces/local. These packs are diagnostic artifacts,
not accepted installations. Existing destinations are refused.
"""
import argparse,copy,hashlib,json,shutil
from pathlib import Path
from .adventurer_digital import TARGET
from .adventurer_source import prepare_source
from .sdk_compile_reference import validate_source

ROOT=Path(__file__).resolve().parents[1]
NAMES={'renamed_factory':'ewrcompass_ctl01@LC',
       'factory_plus_seconds':'ewrcompass_ctl02@LC',
       'cropped_original_compass':'ewrcompass_ctl03@LC'}


def control_model(model,kind):
    if kind not in NAMES:raise ValueError('Unknown offline control')
    expected='ewrcompass_24d08@LC' if kind=='cropped_original_compass' else TARGET
    if model.get('name')!=expected or model.get('platform')!='ats3089C' or model.get('resolution_ratio')!='466x466':
        raise ValueError('Unexpected control source')
    edited=copy.deepcopy(model);edited['name']=NAMES[kind]
    if kind=='factory_plus_seconds':
        edited['item'].append({'widget':'text','type':'second','x':205,'y':253,
            'w':56,'h':26,'font':'Hr','fontnum':10,'enable_font':0,
            'min_numwidth':2,'align':'center'})
    elif kind=='cropped_original_compass':
        edited['item']=[x for x in edited['item'] if not (
            x.get('type')=='compass_icon' and x.get('picture')=='WAngle_8888.png' or
            x.get('widget')=='text' and x.get('type')=='angle' and x.get('font')=='WData')]
    return edited


def asset_manifest(source):
    return {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.rglob('*') if p.is_file() and p.relative_to(source)!=Path('firmware/dial.json')}


def prepare_controls(source,destination):
    source,model=validate_source(source);destination=Path(destination).absolute()
    if not destination.resolve().is_relative_to(ROOT/'faces/local'):
        raise ValueError('Vendor source controls must remain under ignored faces/local')
    if destination.exists() or destination.is_symlink():raise FileExistsError('New destination required')
    if model.get('name')!=TARGET:raise ValueError('Original factory source required')
    paths=list(source.rglob('*'))
    if len(paths)>1024 or sum(p.stat().st_size for p in paths if p.is_file())>32*1024*1024:
        raise ValueError('Source exceeds bounds')
    destination.mkdir(parents=True);report={}
    original_assets=asset_manifest(source)
    for kind in NAMES:
        output=destination/kind
        if kind=='cropped_original_compass':
            prepare_source(source,output,revision=8)
            base=json.loads((output/'firmware/dial.json').read_bytes())
            before_assets=asset_manifest(output)
        else:
            shutil.copytree(source,output);base=model;before_assets=original_assets
        edited=control_model(base,kind)
        (output/'firmware/dial.json').write_text(json.dumps(edited,indent=2)+'\n')
        if asset_manifest(output)!=before_assets:raise ValueError('Control unexpectedly changed assets')
        report[kind]={'name':edited['name'],'asset_count':len(before_assets),
                      'source_model_sha256':hashlib.sha256(json.dumps(base,sort_keys=True).encode()).hexdigest(),
                      'control_model_sha256':hashlib.sha256(json.dumps(edited,sort_keys=True).encode()).hexdigest(),
                      'normal_widget_count':len(edited['item']),'aod_widget_count':len(edited['fade_item']),
                      'assets_preserved_relative_to_control_base':True,'installation_supported':False}
    return {'kind':'offline_control_sources','controls':report,'physical_device_access':False,
            'runtime_results':'Unknown; compile/structural checks do not emulate watch firmware'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path)
    p.add_argument('--destination',required=True,type=Path);a=p.parse_args()
    try:print(json.dumps(prepare_controls(a.source,a.destination),indent=2));return 0
    except (OSError,ValueError,KeyError):print(json.dumps({'error':'Invalid source or destination; controls not installed'}));return 2


if __name__=='__main__':raise SystemExit(main())
