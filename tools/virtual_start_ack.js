// Emulator-only parser probe: a synthetic successful upload-start callback.
// Never selects a physical address and never sends a remote GATT write.
import Java from 'frida-java-bridge';
Java.perform(() => {
  Java.choose('android.bluetooth.BluetoothGatt', {
    onMatch(gatt) {
      if (gatt.getDevice().getAddress().toString() !== 'F2:F1:F0:00:00:04') return;
      const service = gatt.getService(Java.use('java.util.UUID').fromString('00000ff0-0000-1000-8000-00805f9b34fb'));
      if (service === null) return;
      const characteristic = service.getCharacteristic(Java.use('java.util.UUID').fromString('00000002-0000-1000-8000-00805f9b34fb'));
      if (characteristic === null) return;
      characteristic.setValue(Java.array('byte', [-47,0,0,0,0,0,0,0,0,0,0]));
      const callback = gatt.mCallback.value;
      callback.onCharacteristicChanged(gatt, characteristic);
      send({event: 'virtual_start_ack_injected', size: 11});
    },
    onComplete() {}
  });
});
