"""Reacquire pinned public artifacts from project manifests; never installs APKs."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen, Request

ALLOWED_HOSTS = {'raw.githubusercontent.com', 'github.com', 'd.apkpure.net',
                 'dl.google.com', 'download.mptech.eu', 'hammerphones.com',
                 'play.google.com', 'fccid.io', 'manuals.plus', 'apps.apple.com',
                 'codeload.github.com', 'creekwearable.github.io'}
LIMIT = 512 * 1024 * 1024


def fetch(record, root):
    """Only destinations under private/; hashes are mandatory and checked before rename."""
    relative = Path(record['path'])
    if relative.is_absolute() or '..' in relative.parts or relative.parts[:1] != ('private',):
        raise ValueError('Artifact destination must be inside private/')
    parsed = urlsplit(record['url'])
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise ValueError('Source must use HTTPS on an approved public host')
    expected = record['sha256']
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('Invalid expected SHA-256')
    root = Path(root).resolve()
    dest = root / relative
    if not dest.resolve().is_relative_to(root / 'private'):
        raise ValueError('Destination resolves outside private/')
    if dest.exists():
        if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == expected:
            return {'path': str(relative), 'status': 'already_verified'}
        raise ValueError('Existing artifact differs; move it aside explicitly')
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as out:
            temporary = Path(out.name)
            digest, size = hashlib.sha256(), 0
            with urlopen(Request(record['url'], headers={'User-Agent': 'HAMMER-RE/0.1'}), timeout=60) as response:
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > LIMIT:
                        raise ValueError('Download exceeds limit')
                    out.write(chunk);digest.update(chunk)
            if digest.hexdigest() != expected or size != record['bytes']:
                raise ValueError('Download hash or size mismatch; source may have changed')
        # Hard link gives exclusive destination creation (no overwrites).
        import os
        os.link(temporary, dest)
        return {'path': str(relative), 'status': 'downloaded_and_verified'}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--path',help='Fetch only this exact manifest artifact path')
    args=p.parse_args()
    try:
        records=json.loads(args.manifest.read_text())['artifacts']
        if args.path:
            records=[r for r in records if r['path']==args.path]
            if not records:raise ValueError('Path absent from manifest')
        for record in records:print(json.dumps(fetch(record,args.root)))
        return 0
    except Exception as exc:
        # Do not log redirect URLs, server bodies or other unexpected remote content.
        print(json.dumps({'error_type':type(exc).__name__,'status':'failed'}))
        return 2


if __name__=='__main__':raise SystemExit(main())
