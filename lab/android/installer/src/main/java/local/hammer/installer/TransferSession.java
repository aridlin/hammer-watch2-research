package local.hammer.installer;

import java.util.*;

/** Pure-Java, ACK-gated state machine. No retries, resume, delete or OTA. */
public final class TransferSession {
    public enum Stage { DEVICE, DIAL, MTU, START, DATA, END, VERIFY, DONE, FAILED }
    public Stage stage=Stage.DEVICE;
    public final byte[] data; public final String filename;
    public int offset=0,crc=0; public boolean activeVerified=false;
    private int sentOffset=0,sentCrc=0,chunk;
    private byte[] lastAck;
    private final Map<Integer,Integer> committedAcks=new HashMap<>();
    public boolean transferAccepted=false;
    private final Wire.Assembly assembly=new Wire.Assembly();
    public TransferSession(byte[] data,String filename,int attMtu){
        if(!Wire.validateContainer(data).equals(filename)||attMtu<43)throw new IllegalArgumentException("Face or negotiated Bluetooth MTU unsupported");
        this.data=data;this.filename=filename;chunk=Math.min(180,attMtu-5);
    }
    public byte[] first(){return Wire.DEVICE.clone();}
    public byte[] accept(byte[] value){
        if(stage==Stage.FAILED||stage==Stage.DONE)return null;
        try {
            if(stage==Stage.DEVICE||stage==Stage.DIAL||stage==Stage.MTU||stage==Stage.VERIFY){
                byte[] request=stage==Stage.DEVICE?Wire.DEVICE:stage==Stage.MTU?Wire.MTU:Wire.DIAL;
                if(value.length<2||(value[0]!=(byte)0xc1&&value[0]!=(byte)0xc2&&value[0]!=(byte)0xc3)||(value[1]&127)!=(request[1]&127))return null;
                byte[] packet=assembly.feed(value);if(packet==null)return null;
                // Unrelated async messages are ignored, never treated as acceptance.
                if((packet[1]&127)!=(request[1]&127)||packet[4]!=request[4]||packet[5]!=request[5])return null;
                Wire.Proto p=new Wire.Proto(Wire.body(packet,request));
                if(stage==Stage.DEVICE){
                    if(p.number(1)!=2039||p.number(2)!=2||p.number(3)!=0||p.number(4)!=12||p.number(6)!=3||p.number(21)!=72)throw new IllegalArgumentException("This build supports HW2 model 2039, firmware 2.0.12, orange variant only");
                    stage=Stage.DIAL;return Wire.DIAL.clone();
                }
                if(stage==Stage.DIAL){
                    if(p.number(3)!=8||p.number(15)!=4)throw new IllegalArgumentException("Unsupported watch-face framework");
                    List<byte[]> entries=p.bytes(10);
                    if(p.number(18)<=entries.size())throw new IllegalArgumentException("Watch face slots are full");
                    long free=p.number(11)-p.number(12)-p.number(13),required=((data.length+65535L)/65536)*65536;
                    if(free<required)throw new IllegalArgumentException("Insufficient watch storage");
                    for(byte[] entry:entries)if(canonical(new Wire.Proto(entry).text(4)).equals(canonical(filename)))throw new IllegalArgumentException("This face already exists. Overwriting is disabled");
                    stage=Stage.MTU;return Wire.MTU.clone();
                }
                if(stage==Stage.MTU){if(p.number(2)<40)throw new IllegalArgumentException("Unsupported transfer MTU");stage=Stage.START;return Wire.start(data,filename);}
                boolean present=false;for(byte[] entry:p.bytes(10))if(canonical(new Wire.Proto(entry).text(4)).equals(canonical(filename)))present=true;
                activeVerified=present&&canonical(p.text(14)).equals(canonical(filename));
                stage=Stage.DONE;return null;
            }
            if(value.length<1||Wire.u8(value[0])<0xd1||Wire.u8(value[0])>0xd4)return null;
            if(Arrays.equals(value,lastAck))return null;
            int expected=stage==Stage.START?0xd1:stage==Stage.DATA?0xd2:0xd4;
            if(Wire.u8(value[0])!=expected)return null;
            if(expected==0xd2&&value.length==11&&value[2]==0){
                long oldOffset=Wire.u32(value,3);Integer known=oldOffset<=Integer.MAX_VALUE?committedAcks.get((int)oldOffset):null;
                if(known!=null&&Wire.u32(value,7)==known)return null;
            }
            Wire.ack(value,expected,stage==Stage.DATA,sentOffset,sentCrc);lastAck=value.clone();
            if(stage==Stage.END){transferAccepted=true;stage=Stage.VERIFY;return Wire.DIAL.clone();}
            if(stage==Stage.DATA){offset=sentOffset;crc=sentCrc;committedAcks.put(offset,crc);}
            if(offset==data.length){stage=Stage.END;return Wire.end(crc);}
            int size=Math.min(chunk,data.length-offset);sentOffset=offset+size;sentCrc=Wire.crc16(data,offset,size,crc);
            stage=Stage.DATA;return Wire.block(data,offset,size);
        } catch(RuntimeException failure){stage=Stage.FAILED;throw failure;}
    }
    public static String canonical(String text){int zero=text.indexOf('\0');if(zero>=0)text=text.substring(0,zero);return text.endsWith(".bin")?text.substring(0,text.length()-4):text;}
    public void abort(){stage=Stage.FAILED;}
}
