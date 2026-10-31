// Emulator-only observer: records selected event names and byte counts.
// No return values, arguments or authentication state are changed.
import Java from 'frida-java-bridge';
Java.perform(() => {
  const Plugin = Java.use('com.boskokg.flutter_blue_plus.FlutterBluePlusPlugin');
  const invoke = Plugin.invokeMethodUIThread.overload('java.lang.String', '[B');
  const allowed = new Set(['OnCharacteristicChanged', 'WriteCharacteristicResponse',
    'SetNotificationResponse', 'DiscoverServicesResult', 'DeviceState']);
  invoke.implementation = function(name, payload) {
    const event = name.toString();
    if (allowed.has(event)) send({event, size: payload === null ? 0 : payload.length});
    return invoke.call(this, name, payload);
  };
  send({event: 'observer_ready'});
});
