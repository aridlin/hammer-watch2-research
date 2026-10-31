"""Offline artifact inspection; unknown signatures are observations, not format IDs."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

MAX_INPUT = 512 * 1024 * 1024
MAX_MEMBER = 256 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_RATIO = 1000
SIGNATURES = {"png": b"\x89PNG\r\n\x1a\n", "jpeg": b"\xff\xd8\xff",
              "zip": b"PK\x03\x04", "gzip": b"\x1f\x8b", "elf": b"\x7fELF",
              "dex": b"dex\n", "xz": b"\xfd7zXZ\x00", "AOTA_candidate": b"AOTA"}


def checked_path(value):
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")
    if path.stat().st_size > MAX_INPUT:
        raise ValueError("Input exceeds 512 MiB limit")
    return path


def read_bounded(stream, limit):
    data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Decompressed member exceeds limit")
    return data


def is_capture(path, sample):
    return (path.suffix.lower() in {'.pcap', '.pcapng', '.btsnoop'} or
            sample.startswith((b'btsnoop\x00', b'\xd4\xc3\xb2\xa1', b'\xa1\xb2\xc3\xd4',
                               b'\x4d\x3c\xb2\xa1', b'\xa1\xb2\x3c\x4d', b'\x0a\x0d\x0d\x0a')))


def inventory(path, include_strings=False, sample_bytes=8 * 1024 * 1024):
    path = checked_path(path)
    sha, counts, size = hashlib.sha256(), Counter(), 0
    sample = bytearray()
    with path.open('rb') as f:
        while chunk := f.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_INPUT:
                raise ValueError("Input grew beyond limit")
            sha.update(chunk)
            counts.update(chunk)
            if len(sample) < sample_bytes:
                sample.extend(chunk[:sample_bytes - len(sample)])
    entropy = -sum((n / size) * math.log2(n / size) for n in counts.values()) if size else 0.0
    signatures = []
    for name, magic in SIGNATURES.items():
        start, hits = 0, 0
        while hits < 64:
            offset = sample.find(magic, start)
            if offset < 0:
                break
            signatures.append({'candidate': name, 'offset': offset})
            start, hits = offset + 1, hits + 1
    result = {'schema_version': 1, 'file': path.name, 'size': size,
              'sha256': sha.hexdigest(), 'entropy_bits_per_byte': entropy,
              'header_hex': None if is_capture(path, sample) else sample[:64].hex(),
              'capture_content_redacted': is_capture(path, sample), 'scan_bytes': len(sample),
              'signatures': sorted(signatures, key=lambda x: x['offset'])}
    if include_strings:
        if is_capture(path, sample):
            raise ValueError("Raw capture string output is disabled; keep captures private")
        strings = []
        for match in re.finditer(rb'[\x20-\x7e]{6,256}', sample):
            strings.append({'offset': match.start(), 'text': match.group().decode('ascii')})
            if len(strings) >= 200:
                break
        result['ascii_strings'] = strings
    return result


def zip_entries(z):
    entries = z.infolist()
    if len(entries) > MAX_ENTRIES:
        raise ValueError("Too many archive entries")
    total, seen = 0, set()
    for entry in entries:
        name = entry.filename
        pure = PurePosixPath(name)
        if ('\\' in name or '\x00' in name or pure.is_absolute() or
                '..' in pure.parts or ':' in name or not pure.parts):
            raise ValueError("Unsafe archive path")
        normalized = str(pure).casefold()
        if normalized in seen:
            raise ValueError("Duplicate archive path")
        seen.add(normalized)
        kind = stat.S_IFMT(entry.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError("Archive links and special files are forbidden")
        if entry.flag_bits & 1:
            raise ValueError("Encrypted archive entries are unsupported")
        total += entry.file_size
        if entry.file_size > MAX_MEMBER or total > MAX_TOTAL:
            raise ValueError("Archive uncompressed size exceeds limit")
        if entry.file_size / max(1, entry.compress_size) > MAX_RATIO:
            raise ValueError("Archive compression ratio exceeds limit")
    return entries


def extract(path, destination):
    path = checked_path(path)
    dest = Path(destination).absolute()
    if dest.exists() or dest.is_symlink():
        raise ValueError("Output destination must not exist")
    if not dest.parent.is_dir():
        raise ValueError("Output parent must already exist")
    with zipfile.ZipFile(path) as z:
        entries = zip_entries(z)  # Validate every path before creating output.
        temporary = Path(tempfile.mkdtemp(prefix='.hammer-extract-', dir=dest.parent))
        try:
            for entry in entries:
                out = temporary.joinpath(*PurePosixPath(entry.filename).parts)
                if entry.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as src, out.open('xb') as dst:
                    written = 0
                    while chunk := src.read(1024 * 1024):
                        written += len(chunk)
                        if written > entry.file_size or written > MAX_MEMBER:
                            raise ValueError("Member exceeded declared size")
                        dst.write(chunk)
                    if written != entry.file_size:
                        raise ValueError("Member size mismatch")
            # Exclusive directory creation prevents replacing an existing destination.
            dest.mkdir()
            try:
                for child in temporary.iterdir():
                    shutil.move(str(child), dest / child.name)
            except Exception:
                shutil.rmtree(dest)
                raise
        finally:
            shutil.rmtree(temporary)
    return {'destination': str(dest), 'entries': len(entries)}


def android_identity(raw):
    try:
        from androguard.core.apk import APK
        from loguru import logger
        logger.disable('androguard')
    except ImportError:
        return {'status': 'unavailable', 'reason': 'Install the pinned android extra for AXML and signing inspection'}
    try:
        apk = APK(raw, raw=True)
        if not apk.is_valid_APK():
            return {'status': 'invalid', 'reason': 'Manifest could not be validated'}
        certs = [cert.dump() for cert in apk.get_certificates()]
        return {'status': 'parsed', 'package': apk.get_package(),
                'version_name': apk.get_androidversion_name(), 'version_code': apk.get_androidversion_code(),
                'certificate_sha256': sorted({hashlib.sha256(c).hexdigest() for c in certs}),
                'signature_schemes_present': {'v1': apk.is_signed_v1(), 'v2': apk.is_signed_v2(), 'v3': apk.is_signed_v3()},
                'cryptographic_verification': 'not performed; use apksigner verify',
                'authenticity': 'unverified without trusted Play certificate comparison'}
    except Exception as exc:
        return {'status': 'analysis_error', 'reason': type(exc).__name__}


def apk_summary(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries = zip_entries(z)
        names = [e.filename for e in entries]
        if 'AndroidManifest.xml' not in names:
            raise ValueError('APK missing AndroidManifest.xml')
        result = {'sha256': hashlib.sha256(raw).hexdigest(),
                  'identity': android_identity(raw), 'member_count': len(entries),
                  'members': [{'name': e.filename, 'size': e.file_size, 'compressed_size': e.compress_size,
                               'crc32': f'{e.CRC:08x}'} for e in entries],
                  'dex': [n for n in names if re.fullmatch(r'classes\d*\.dex', n)],
                  'native_libraries': [n for n in names if n.startswith('lib/') and n.endswith('.so')],
                  'flutter_assets_present': any('flutter_assets/' in n for n in names),
                  'candidate_resources': [n for n in names if any(k in n.lower() for k in
                     ('dial', 'watchface', '.bin', '.dat', '.proto', 'flutter_assets'))][:500]}
    return result


def inspect_apk(path):
    path = checked_path(path)
    with zipfile.ZipFile(path) as z:
        entries = zip_entries(z)
        names = [e.filename for e in entries]
        if 'AndroidManifest.xml' in names:
            return {'kind': 'apk', **apk_summary(path.read_bytes())}
        nested = [e for e in entries if e.filename.lower().endswith('.apk')]
        if not nested:
            raise ValueError('No APKs found in archive')
        # Nested archive budgets aggregate across the entire bundle.
        total, count, results = 0, 0, []
        for entry in nested:
            with z.open(entry) as stream:
                raw = read_bounded(stream, MAX_MEMBER)
            with zipfile.ZipFile(io.BytesIO(raw)) as child:
                child_entries = zip_entries(child)
                total += sum(e.file_size for e in child_entries)
                count += len(child_entries)
                if total > MAX_TOTAL or count > MAX_ENTRIES:
                    raise ValueError('Nested archive aggregate limit exceeded')
            results.append({'name': entry.filename, **apk_summary(raw)})
        identities = [r['identity'] for r in results]
        certs = [r.get('certificate_sha256', []) for r in identities]
        comparable = all(r.get('status') == 'parsed' for r in identities) and all(certs)
        return {'kind': 'apk_bundle', 'apks': results,
                'split_certificate_consistency': ('consistent' if all(c == certs[0] for c in certs) else 'mismatch') if comparable else 'unverified',
                'package_consistency': len({r.get('package') for r in identities}) == 1 if comparable else None}


def compare(a, b, max_ranges=200):
    a, b = checked_path(a), checked_path(b)
    different = same = 0
    start = None
    ranges = []
    total_ranges = 0
    offset = 0
    with a.open('rb') as fa, b.open('rb') as fb:
        while True:
            ca, cb = fa.read(65536), fb.read(65536)
            if not ca and not cb:
                break
            for i in range(max(len(ca), len(cb))):
                equal = i < len(ca) and i < len(cb) and ca[i] == cb[i]
                if equal:
                    same += 1
                    if start is not None:
                        if len(ranges) < max_ranges:
                            ranges.append({'start': start, 'end_exclusive': offset})
                        total_ranges += 1
                        start = None
                else:
                    different += 1
                    if start is None:
                        start = offset
                offset += 1
        if start is not None:
            if len(ranges) < max_ranges:
                ranges.append({'start': start, 'end_exclusive': offset})
            total_ranges += 1
    return {'same_offset_equal_bytes': same, 'different_or_missing_bytes': different,
            'same_offset_similarity': same / offset if offset else 1.0,
            'different_ranges': ranges, 'range_count': total_ranges,
            'ranges_truncated': total_ranges > len(ranges),
            'alignment': 'same-offset only; insertions are not realigned'}


def doctor():
    programs = {}
    for name in ('python3', 'java', 'adb', 'jadx', 'apktool', 'apksigner', 'tshark', 'unzip', 'git', 'uv'):
        exe = shutil.which(name)
        item = {'path': exe}
        if exe:
            flag = {'java': '-version', 'adb': 'version', 'unzip': '-v'}.get(name, '--version')
            try:
                p = subprocess.run([exe, flag], capture_output=True, text=True, timeout=10)
                item.update(version=(p.stdout or p.stderr).splitlines()[:2], exit_code=p.returncode)
            except (OSError, subprocess.TimeoutExpired) as exc:
                item['error'] = type(exc).__name__
        programs[name] = item
    packages = {}
    for name in ('androguard', 'Pillow', 'pytest'):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {'python': sys.version.split()[0], 'programs': programs, 'packages': packages,
            'device_access': 'none; doctor does not enumerate or connect devices'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New JSON file; refuses overwrite')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    inv = sub.add_parser('inventory')
    inv.add_argument('file')
    inv.add_argument('--strings', action='store_true', help='Opt in to private ASCII previews (never commit unreviewed)')
    apk = sub.add_parser('apk-inspect')
    apk.add_argument('file')
    comp = sub.add_parser('compare')
    comp.add_argument('a')
    comp.add_argument('b')
    ext = sub.add_parser('extract')
    ext.add_argument('file')
    ext.add_argument('--destination', required=True)
    args = parser.parse_args(argv)
    try:
        if args.output and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError('Output already exists')
        if args.command == 'doctor': result = doctor()
        elif args.command == 'inventory': result = inventory(args.file, args.strings)
        elif args.command == 'apk-inspect': result = inspect_apk(args.file)
        elif args.command == 'compare': result = compare(args.a, args.b)
        else: result = extract(args.file, args.destination)
        data = json.dumps(result, indent=2, ensure_ascii=True) + '\n'
        if args.output:
            with args.output.open('x') as f: f.write(data)
        else:
            print(data, end='')
        return 0
    except (ValueError, OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError) as exc:
        print(json.dumps({'error': str(exc), 'type': type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
