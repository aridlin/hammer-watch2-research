"""Generate separate local APK/package signing keys; never print private values."""
import argparse,hashlib,os,secrets,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def initialize(destination,keytool):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    destination=Path(destination).absolute()
    if not destination.resolve().is_relative_to(ROOT/'private'):raise ValueError('Signing material must stay under private/')
    if destination.exists() or destination.is_symlink():raise FileExistsError('Key directory already exists; never replace signing keys')
    if not keytool:raise ValueError('JDK keytool is required')
    destination.mkdir(parents=True,mode=0o700);(destination/'assets').mkdir()
    def secret_file(name,data):
        with os.fdopen(os.open(destination/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as out:out.write(data)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    secret_file('face-signing.pem',key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    public=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    (destination/'assets/face-signing-public.der').write_bytes(public)
    password=secrets.token_urlsafe(30)
    secret_file('signing.properties',f'storePassword={password}\nkeyPassword={password}\nkeyAlias=hammer-installer\n'.encode())
    secret_file('temporary-password',password.encode())
    try:
        result=subprocess.run([str(keytool),'-genkeypair','-keystore',str(destination/'app-release.keystore'),'-storepass:file',str(destination/'temporary-password'),'-keypass:file',str(destination/'temporary-password'),'-alias','hammer-installer','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=HAMMER Face Installer'],capture_output=True,timeout=60)
        if result.returncode:raise ValueError('Local key generation failed; preserve partial directory for inspection')
        (destination/'app-release.keystore').chmod(0o600)
    finally:(destination/'temporary-password').unlink(missing_ok=True)
    return {'keys_created':True,'public_package_key_sha256':hashlib.sha256(public).hexdigest(),'private_values_printed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--destination',type=Path,default=ROOT/'private/installer');p.add_argument('--keytool',type=Path,default=shutil.which('keytool'));a=p.parse_args()
    try:
        import json
        print(json.dumps(initialize(a.destination,a.keytool)));return 0
    except (OSError,ValueError,subprocess.SubprocessError):print('{"error":"Key preparation failed; no private values printed"}');return 2


if __name__=='__main__':raise SystemExit(main())
