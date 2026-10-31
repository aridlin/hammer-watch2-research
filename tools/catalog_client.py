"""Narrow, read-only catalog client. Session files and responses stay local.

No login, refresh, binding, upload, update or device-write operation is exposed.
The session is obtained from the user's own signed-in lab, never via CLI secrets.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.request

BASE_URL = 'https://cloud-frankfurt.creekcould.com'
ENDPOINTS = {
    'bluetooth-names': '/service-device/v1/device/bluetooth',
    'faces': '/service-parts/v1/dial/listFirmware',
}
MAX_RESPONSE = 8 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused; session headers must not leave the selected host')


def load_session(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Session must be an ordinary local file')
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Session file must have private permissions (chmod 600)')
    if path.stat().st_size > 65536:
        raise ValueError('Session file too large')
    session = json.loads(path.read_text())
    if session.get('base_url') != BASE_URL:
        raise ValueError('Only the observed Frankfurt API authority is enabled')
    token = session.get('authorization')
    if not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise ValueError('Invalid session authorization value')
    if not isinstance(session.get('app_info'), dict):
        raise ValueError('Missing app metadata')
    return session


def make_request(session, operation, compatibility=None):
    if operation not in ENDPOINTS:
        raise ValueError('Unsupported read-only operation')
    body = {}
    if operation == 'faces':
        required = {'firmwareId', 'appFrameVersion', 'firmwareFrameVersion', 'customerCode', 'snCode'}
        if not isinstance(compatibility, dict) or set(compatibility) != required:
            raise ValueError('Provide all five compatibility fields from verified device evidence')
        for key in ('firmwareId', 'appFrameVersion', 'firmwareFrameVersion'):
            if type(compatibility[key]) is not int or compatibility[key] <= 0:
                raise ValueError('Compatibility identifiers must be positive integers')
        if not isinstance(compatibility['customerCode'], str):
            raise ValueError('Invalid customer code')
        # AllDialListRequestModel.toJson boxes an untagged int64 at field_23.
        # snCode is a device code, not the displayed personal serial number.
        if type(compatibility['snCode']) is not int or not 0 <= compatibility['snCode'] < 2**63:
            raise ValueError('snCode must be a nonnegative integer device code')
        body = compatibility
    return urllib.request.Request(BASE_URL + ENDPOINTS[operation],
        data=json.dumps(body, separators=(',', ':')).encode(),
        headers={'Content-Type': 'application/json', 'Lang-Code': 'en',
                 'Authorization': session['authorization'],
                 'App-Info': json.dumps(session['app_info'], separators=(',', ':'))}, method='POST')


def fetch(request, opener=None):
    opener = opener or urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=30) as response:
        data = response.read(MAX_RESPONSE + 1)
    if len(data) > MAX_RESPONSE:
        raise ValueError('Response exceeds limit')
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError('Unexpected response envelope')
    return result


def save_private(path, result):
    path = Path(path)
    # Output is explicitly restricted to the ignored local-auth area.
    root = (Path(__file__).resolve().parents[1] / 'private/auth').resolve()
    if not path.resolve().is_relative_to(root):
        raise ValueError('Responses must stay under private/auth')
    path.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        json.dump(result, f, ensure_ascii=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=ENDPOINTS)
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--compatibility', type=Path)
    p.add_argument('--destination', type=Path, required=True)
    a = p.parse_args()
    try:
        if a.destination.exists():
            raise ValueError('Destination exists')
        session = load_session(a.session)
        compatibility = json.loads(a.compatibility.read_text()) if a.compatibility else None
        result = fetch(make_request(session, a.operation, compatibility))
        save_private(a.destination, result)
        # Server messages can echo credentials. Never print bodies or exceptions.
        print(json.dumps({'operation': a.operation, 'application_code': result.get('code'),
                          'saved_privately': True}))
        return 0 if result.get('code') == 200 else 1
    except (OSError, ValueError, urllib.error.URLError):
        print(json.dumps({'error': 'Request failed; no response or credential values printed'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
