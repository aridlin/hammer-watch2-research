// Synthetic receiver callbacks for Netsim identity04, confined to the debug app.
// Original GATT writes proceed unchanged to Netsim; nothing is bridged to hardware.
import Java from 'frida-java-bridge';
Java.perform(() => {
  const Gatt = Java.use('android.bluetooth.BluetoothGatt');
  const UUID = Java.use('java.util.UUID');
  let expected = 0, received = 0, crc = 0, active = false, blocks = 0, inside = false;
  function reply(gatt, opcode, sequence, offset, checksum) {
    const service = gatt.getService(UUID.fromString('00000ff0-0000-1000-8000-00805f9b34fb'));
    if (service === null) return;
    const notify = service.getCharacteristic(UUID.fromString('00000002-0000-1000-8000-00805f9b34fb'));
    if (notify === null) return;
    const data = [opcode, sequence, 0];
    for (let i=0; i<4; ++i) data.push((offset >>> (8*i)) & 255);
    for (let i=0; i<4; ++i) data.push((checksum >>> (8*i)) & 255);
    notify.setValue(Java.array('byte',data.map(x=>x>127?x-256:x)));
    gatt.mCallback.value.onCharacteristicChanged(gatt,notify);
  }
  function u32(bytes,offset) {return (bytes[offset]|(bytes[offset+1]<<8)|(bytes[offset+2]<<16)|(bytes[offset+3]<<24))>>>0;}
  for (const method of Gatt.writeCharacteristic.overloads) {
    method.implementation = function (...args) {
      if (inside) return method.apply(this,args);
      let result;inside=true;
      try {result=method.apply(this,args);} finally {inside=false;}
      try {
        if (this.getDevice().getAddress().toString() !== 'F2:F1:F0:00:00:04') return result;
        if (args[0].getUuid().toString() !== '00000001-0000-1000-8000-00805f9b34fb') return result;
        const raw = args.length===3 ? args[1] : args[0].getValue();
        const bytes=Array.from(raw,x=>Number(x)&255);
        if (bytes.length<2 || bytes.length>514) return result;
        const opcode=bytes[0],sequence=bytes[1];
        if (opcode===0xd1) {
          const name=String.fromCharCode(...bytes.slice(11)).replace(/\x00+$/,'');
          if (bytes.length!==34 || name!=='ewrcompass_0819@LC.bin') return result;
          expected=u32(bytes,2);received=0;crc=0;blocks=0;active=expected>0 && expected<1024*1024;
          if (!active) return result;
          send({event:'virtual_transfer_start',size:expected});
        } else if (opcode===0xd2 && active) {
          if (received+bytes.length-2>expected) {active=false;return result;}
          for (const b of bytes.slice(2)) {
            crc^=b<<8;
            for (let i=0;i<8;++i) crc=((crc&0x8000)?(crc<<1)^0x1021:crc<<1)&65535;
          }
          received+=bytes.length-2;blocks++;
          if (blocks%100===0) send({event:'virtual_transfer_progress',size:received});
        } else if (opcode===0xd3 && active) {
          // Resume-position response only within this synthetic stream.
        } else if (opcode===0xd4 && active && received===expected) {
          send({event:'virtual_transfer_end',size:received});active=false;
        } else return result;
        const gatt=Java.retain(this),position=received,checksum=crc;
        setTimeout(()=>Java.perform(()=>{
          try {reply(gatt,opcode,sequence,position,checksum);} finally {gatt.$dispose();}
        }),20);
      } catch (_) {send({event:'virtual_transfer_probe_error'});}
      return result;
    };
  }
  send({event:'observer_ready'});
});
