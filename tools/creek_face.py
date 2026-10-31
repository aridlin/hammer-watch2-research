"""Inspect observed Creek source ZIPs. Does not generate watch-installable binaries."""
import argparse
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

from .hammer_re import checked_path, read_bounded, zip_entries

JSON_LIMIT = 4 * 1024 * 1024


def inspect_source(path):
    path = checked_path(path)
    docs = []
    with zipfile.ZipFile(path) as z:
        entries = zip_entries(z)
        for entry in entries:
            p = PurePosixPath(entry.filename)
            if p.name != 'dial.json' or '__MACOSX' in p.parts:
                continue
            with z.open(entry) as stream:
                raw = read_bounded(stream, JSON_LIMIT)
            model = json.loads(raw)
            if not isinstance(model, dict):
                raise ValueError('dial.json must be an object')
            layers = {}
            for key in ['item', 'fade_item']:
                items = model.get(key, [])
                if not isinstance(items, list) or any(not isinstance(i, dict) for i in items):
                    raise ValueError(f'{key} must be a list of objects')
                layers[key] = {'count': len(items),
                               'types': dict(Counter(str(i.get('type', '<absent>')) for i in items)),
                               'widgets': dict(Counter(str(i.get('widget', '<absent>')) for i in items))}
            assets = [e for e in entries if e.filename.startswith(str(p.parent) + '/') and not e.is_dir()]
            docs.append({'member': entry.filename, 'sha256': hashlib.sha256(raw).hexdigest(),
                         'original_json_base64': base64.b64encode(raw).decode('ascii'),
                         'document': model, 'layers': layers,
                         'assets': [{'member': e.filename, 'size': e.file_size, 'crc32': f'{e.CRC:08x}'} for e in assets]})
    if not docs:
        raise ValueError('No Creek source firmware/dial.json found')
    return {'schema_version': 1, 'kind': 'creek_source_zip',
            'archive_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'compatibility': 'reference sample; HAMMER compatibility unverified',
            'documents': docs}


def restore_json(ir_path, destination, index=0):
    ir_path = checked_path(ir_path)
    if ir_path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('IR exceeds size limit')
    ir = json.loads(ir_path.read_text())
    if ir.get('kind') != 'creek_source_zip' or ir.get('schema_version') != 1:
        raise ValueError('Unsupported IR schema')
    if index < 0 or index >= len(ir['documents']):
        raise ValueError('Document index out of range')
    doc = ir['documents'][index]
    raw = base64.b64decode(doc['original_json_base64'], validate=True)
    if len(raw) > JSON_LIMIT or hashlib.sha256(raw).hexdigest() != doc['sha256']:
        raise ValueError('Original metadata hash mismatch')
    if json.loads(raw) != doc['document']:
        raise ValueError('Edited IR cannot be restored as byte-identical original metadata')
    with Path(destination).open('xb') as out:
        out.write(raw)
    return {'destination': str(destination), 'sha256': doc['sha256'],
            'result': 'byte-identical source JSON only; not a compiled dial'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, help='New JSON report; refuses overwrite')
    sub = p.add_subparsers(dest='command', required=True)
    ins = sub.add_parser('inspect')
    ins.add_argument('archive')
    res = sub.add_parser('restore-json')
    res.add_argument('ir')
    res.add_argument('--destination', required=True)
    res.add_argument('--index', type=int, default=0)
    args = p.parse_args(argv)
    try:
        if args.output and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError('Output already exists')
        result = inspect_source(args.archive) if args.command == 'inspect' else restore_json(args.ir, args.destination, args.index)
        text = json.dumps(result, indent=2, ensure_ascii=True) + '\n'
        if args.output:
            with args.output.open('x') as out: out.write(text)
        else:
            print(text, end='')
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({'error': str(exc), 'type': type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
