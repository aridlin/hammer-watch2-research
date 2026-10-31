"""Run the permission-stripped offline SDK oracle on the dedicated emulator only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from .creek_bin import parse

PACKAGE='local.hammer.compiler'
REMOTE='/data/user/0/local.hammer.compiler/files'
ADB=['adb','-P','5038','-s','emulator-5580']


def adb(*args,check=True):
    return subprocess.run(ADB+list(args),capture_output=True,timeout=90,check=check)


def validate_source(source):
    source=Path(source).resolve()
    model=json.loads((source/'firmware/dial.json').read_bytes())
    if model.get('platform') not in {'ats3085c','ats3085s','ats3089C'} or model.get('resolution_ratio')!='466x466':
        raise ValueError('This fixed oracle accepts only observed ats3085c/ats3085s/ats3089C 466x466 packs')
    # Do not push symlinks or out-of-root paths into the emulator.
    for path in source.rglob('*'):
        if path.is_symlink():raise ValueError('Reference source must not contain symlinks')
    return source,model


def compile_reference(source,destination,apk,timeout=120,platform='JX_3085C_PLATFORM',abi=None):
    from loguru import logger
    from androguard.core.apk import APK
    logger.disable('androguard')
    if platform not in {'JX_3085C_PLATFORM','JX_3085S_PLATFORM'}:raise ValueError('Unsupported offline platform')
    if abi not in {None,'arm64-v8a','x86_64'}:raise ValueError('Unsupported offline ABI')
    source,model=validate_source(source)
    destination=Path(destination).absolute()
    if destination.exists() or destination.is_symlink():raise FileExistsError('Destination must be new')
    if not destination.parent.is_dir():raise ValueError('Destination parent must exist')
    if adb('shell','getprop','ro.kernel.qemu').stdout.strip()!=b'1':
        raise ValueError('Refusing non-emulator target')
    if adb('shell','getprop','ro.build.type').stdout.strip()!=b'userdebug':
        raise ValueError('This oracle requires a userdebug emulator')
    app=APK(str(apk))
    forbidden=[p for p in app.get_permissions() if p=='android.permission.INTERNET' or 'BLUETOOTH' in p]
    if app.get_package()!=PACKAGE or forbidden:
        raise ValueError('Harness package identity or permission isolation check failed')
    install_args=['install','-r']
    if abi:install_args+=['--abi',abi]
    adb(*install_args,str(apk))
    adb('shell','am','force-stop',PACKAGE)
    adb('shell','rm','-rf',REMOTE+'/input')
    adb('shell','rm','-f',REMOTE+'/reference.bin',REMOTE+'/status.txt')
    adb('shell','mkdir','-p',REMOTE+'/input')
    adb('push',str(source)+'/.',REMOTE+'/input/')
    adb('shell','task_compiler_uid=$(stat -c %u /data/user/0/local.hammer.compiler); '
        'chown -R "$task_compiler_uid:$task_compiler_uid" /data/user/0/local.hammer.compiler/files/input; '
        'restorecon -R /data/user/0/local.hammer.compiler/files/input')
    adb('shell','am','start','-W','-n',PACKAGE+'/.MainActivity','--es','platform',platform)
    deadline=time.monotonic()+timeout
    status=''
    while time.monotonic()<deadline:
        status=adb('exec-out','cat',REMOTE+'/status.txt',check=False).stdout.decode(errors='replace')
        if status.startswith('Encoded reference.bin:'):break
        if 'failed:' in status:raise ValueError('SDK reported a compilation failure')
        time.sleep(1)
    else:raise TimeoutError('SDK compiler timed out; inspect private emulator logs')
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as f:temporary=Path(f.name)
        adb('pull',REMOTE+'/reference.bin',str(temporary))
        data=temporary.read_bytes();report=parse(data)
        if report['name']!=model.get('name'):raise ValueError('Returned face name differs from selected source')
        os.link(temporary,destination)
        return {'result':'compiled_offline_no_upload','platform_argument':platform,'process_abi':abi or 'system_selected',
                'target_compatibility':'unverified','source_platform':model['platform'],'destination':str(destination),
                'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
                'crc_valid':report['crc_valid'],'resource_count':report['resource_count']}
    finally:
        if temporary:temporary.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--destination',required=True,type=Path)
    p.add_argument('--apk',type=Path,default=Path('lab/android/app/build/outputs/apk/debug/app-debug.apk'))
    p.add_argument('--platform',choices=['JX_3085C_PLATFORM','JX_3085S_PLATFORM'],default='JX_3085C_PLATFORM')
    p.add_argument('--abi',choices=['arm64-v8a','x86_64'])
    a=p.parse_args()
    try:print(json.dumps(compile_reference(a.source,a.destination,a.apk,platform=a.platform,abi=a.abi),indent=2));return 0
    except (ValueError,OSError,ImportError,TimeoutError,subprocess.SubprocessError) as exc:
        print(json.dumps({'error_type':type(exc).__name__}));return 2


if __name__=='__main__':raise SystemExit(main())
