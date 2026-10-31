from tools.observe_emulator_ble import sanitized_event


def test_observer_rejects_secrets_and_non_events():
    assert sanitized_event({'type':'send','payload':{'event':'Authorization','token':'secret'}}) is None
    assert sanitized_event({'type':'error','description':'private runtime details'}) is None
    assert sanitized_event({'type':'send','payload':{'event':'OnCharacteristicChanged','size':20,'token':'secret','bytes':'secret'}})=={'event':'OnCharacteristicChanged','size':20}
    assert sanitized_event({'type':'send','payload':{'event':'observer_ready','size':True}})=={'event':'observer_ready'}
