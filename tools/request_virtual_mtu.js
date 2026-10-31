// Debug-emulator transport probe only. Never selects a physical watch address.
import Java from 'frida-java-bridge';
Java.perform(() => {
  Java.choose('android.bluetooth.BluetoothGatt', {
    onMatch(gatt) {
      const address = gatt.getDevice().getAddress().toString();
      if (address === 'F2:F1:F0:00:00:04') {
        if (gatt.requestMtu(517)) send({event: 'virtual_mtu_requested', size: 517});
      }
    },
    onComplete() {}
  });
});
