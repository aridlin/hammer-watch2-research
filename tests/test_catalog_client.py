import json
import pytest
from tools.catalog_client import BASE_URL, NoRedirect, load_session, make_request, fetch, MAX_RESPONSE


def session():
    return {'base_url': BASE_URL, 'authorization': 'synthetic-token',
            'app_info': {'appName': 'Hammer%20App', 'appVersion': '1.0.15'}}


def test_private_session_permissions_and_host(tmp_path):
    p = tmp_path/'session.json'
    p.write_text(json.dumps(session())); p.chmod(0o644)
    with pytest.raises(ValueError): load_session(p)
    p.chmod(0o600)
    assert load_session(p)['authorization'] == 'synthetic-token'
    data = session(); data['base_url'] = 'https://example.org'
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_session(p)


def test_request_and_no_mutations_or_guessed_identifiers():
    req = make_request(session(), 'bluetooth-names')
    assert req.data == b'{}'
    assert req.get_header('Authorization') == 'synthetic-token'
    assert json.loads(req.get_header('App-info'))['appName'] == 'Hammer%20App'
    for operation in ('upload', 'bind', 'refresh', 'faces'):
        with pytest.raises(ValueError): make_request(session(), operation)
    body = dict(firmwareId=123, appFrameVersion=9, firmwareFrameVersion=1, customerCode='', snCode=65)
    assert json.loads(make_request(session(), 'faces', body).data) == body
    body['firmwareId'] = True
    with pytest.raises(ValueError): make_request(session(), 'faces', body)


def test_credentials_never_redirected():
    with pytest.raises(ValueError): NoRedirect().redirect_request(None,None,302,'',{},'https://example.org')


def test_response_bounded():
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self, limit): return b'x'*limit
    class Opener:
        def open(self,*args,**kwargs): return Response()
    with pytest.raises(ValueError): fetch(make_request(session(),'bluetooth-names'),Opener())


@pytest.mark.parametrize('code', ['', 'private-serial', True, -1, 2**63])
def test_sn_code_is_integer_device_code_not_serial_number(code):
    body = dict(firmwareId=2039, appFrameVersion=9, firmwareFrameVersion=1,
                customerCode='', snCode=code)
    with pytest.raises(ValueError): make_request(session(), 'faces', body)
