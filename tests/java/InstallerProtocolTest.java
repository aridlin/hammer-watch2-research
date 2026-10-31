import local.hammer.installer.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32;

/** Host Java tests: no Android, Bluetooth stack or vendor SDK. */
public class InstallerProtocolTest {
    static void check(boolean condition){if(!condition)throw new AssertionError();}
    static void rejects(Runnable action){try{action.run();throw new AssertionError("Expected rejection");}catch(IllegalArgumentException expected){}}
    static byte[] concat(byte[]... parts){ByteArrayOutputStream out=new ByteArrayOutputStream();for(byte[] b:parts)out.writeBytes(b);return out.toByteArray();}
    static byte[] integer(int field,long n){ByteArrayOutputStream out=new ByteArrayOutputStream();out.writeBytes(varint(field*8));out.writeBytes(varint(n));return out.toByteArray();}
    static byte[] varint(long n){ByteArrayOutputStream out=new ByteArrayOutputStream();while(n>=128){out.write((int)(n&127)|128);n>>>=7;}out.write((int)n);return out.toByteArray();}
    static byte[] bytes(int field,byte[] b){return concat(varint(field*8+2),varint(b.length),b);}
    static byte[] reply(byte[] request,byte[] body){byte[] p=new byte[13+body.length];System.arraycopy(request,0,p,0,11);p[1]|=(byte)128;p[10]=0;Wire.put32(p,6,11+body.length);System.arraycopy(body,0,p,11,body.length);int crc=Wire.crc16(p,0,p.length-2,65535);p[p.length-2]=(byte)crc;p[p.length-1]=(byte)(crc>>8);return p;}
    static byte[] fixture(){byte[] b=new byte[84];System.arraycopy("test_face01".getBytes(StandardCharsets.US_ASCII),0,b,0,11);Wire.put32(b,30,0x5aa54321L);b[34]=1;b[35]=1;b[37]=1;b[39]=4;System.arraycopy("dial.json".getBytes(StandardCharsets.US_ASCII),0,b,44,9);Wire.put32(b,74,82);Wire.put32(b,78,2);b[82]='{';b[83]='}';CRC32 crc=new CRC32();crc.update(b,44,b.length-44);Wire.put32(b,40,crc.getValue());return b;}
    static byte[] device(int model){return concat(integer(1,model),integer(2,2),integer(4,12),integer(6,3),integer(21,72));}
    static byte[] dial(String filename,boolean active){byte[] base=concat(integer(3,8),integer(15,4),integer(18,24),integer(11,41943040),integer(12,100000));if(filename!=null)base=concat(base,bytes(10,bytes(4,filename.getBytes(StandardCharsets.US_ASCII))),active?bytes(14,filename.getBytes(StandardCharsets.US_ASCII)):new byte[0]);return base;}
    static byte[] ack(int opcode,int offset,int crc){byte[] b=new byte[opcode==0xd2?11:3];b[0]=(byte)opcode;if(b.length==11){Wire.put32(b,3,offset);Wire.put32(b,7,crc);}return b;}
    public static void main(String[] args)throws Exception{
        byte[] fixture=fixture();check(Wire.validateContainer(fixture).equals("test_face01.bin"));
        check(Wire.crc16("123456789".getBytes(),0,9,65535)==0x29b1);check(Wire.crc16("123456789".getBytes(),0,9,0)==0x31c3);
        rejects(()->Wire.validateContainer(new byte[0]));byte[] corrupted=fixture.clone();corrupted[83]^=1;rejects(()->Wire.validateContainer(corrupted));
        // Complete synthetic transfer, duplicates and post-install verification.
        TransferSession session=new TransferSession(fixture,"test_face01.bin",247);check(Arrays.equals(session.first(),Wire.DEVICE));
        check(Arrays.equals(session.accept(reply(Wire.DEVICE,device(2039))),Wire.DIAL));
        check(Arrays.equals(session.accept(reply(Wire.DIAL,dial(null,false))),Wire.MTU));
        byte[] packet=session.accept(reply(Wire.MTU,integer(2,244)));check(packet[0]==(byte)0xd1);check(Wire.ascii(packet,11,packet.length-11).equals("test_face01.bin"));
        packet=session.accept(ack(0xd1,0,0));check(packet[0]==(byte)0xd2);check(session.accept(ack(0xd1,0,0))==null);
        check(Arrays.equals(Arrays.copyOfRange(packet,2,packet.length),fixture));int crc=Wire.crc16(fixture,0,fixture.length,0);
        packet=session.accept(ack(0xd2,fixture.length,crc));check(packet[0]==(byte)0xd4&&Wire.u32(packet,3)==crc);
        check(session.accept(ack(0xd2,fixture.length,crc))==null);check(Arrays.equals(session.accept(ack(0xd4,0,0)),Wire.DIAL));
        check(session.accept(reply(Wire.DIAL,dial("test_face01.bin",true)))==null&&session.stage==TransferSession.Stage.DONE&&session.activeVerified);
        TransferSession bad=new TransferSession(fixture,"test_face01.bin",247);rejects(()->bad.accept(reply(Wire.DEVICE,device(1))));check(bad.stage==TransferSession.Stage.FAILED);
        TransferSession existing=new TransferSession(fixture,"test_face01.bin",247);existing.accept(reply(Wire.DEVICE,device(2039)));rejects(()->existing.accept(reply(Wire.DIAL,dial("test_face01.bin",false))));
        rejects(()->Wire.ack(ack(0xd2,1,0),0xd2,true,84,crc));
        // Late duplicate ACKs may arrive after more than one subsequent block.
        byte[] large=Arrays.copyOf(fixture,800);CRC32 largeCrc=new CRC32();largeCrc.update(large,44,large.length-44);Wire.put32(large,40,largeCrc.getValue());
        TransferSession late=new TransferSession(large,"test_face01.bin",247);
        late.accept(reply(Wire.DEVICE,device(2039)));late.accept(reply(Wire.DIAL,dial(null,false)));late.accept(reply(Wire.MTU,integer(2,244)));late.accept(ack(0xd1,0,0));
        int c180=Wire.crc16(large,0,180,0),c360=Wire.crc16(large,0,360,0);
        late.accept(ack(0xd2,180,c180));late.accept(ack(0xd2,360,c360));
        check(late.accept(ack(0xd2,180,c180))==null&&late.offset==360&&late.stage==TransferSession.Stage.DATA);
        for(int end=540;end<large.length;end+=180)late.accept(ack(0xd2,end,Wire.crc16(large,0,end,0)));
        late.accept(ack(0xd2,large.length,Wire.crc16(large,0,large.length,0)));late.accept(ack(0xd4,0,0));
        byte[] verify=reply(Wire.DIAL,concat(dial("test_face01.bin",true),bytes(40,new byte[620])));
        List<byte[]> verifyParts=new ArrayList<>();verifyParts.add(Arrays.copyOfRange(verify,0,240));int cursor=240;
        while(cursor<verify.length){int count=Math.min(238,verify.length-cursor);byte[] part=new byte[count+2];part[0]=(byte)(cursor+count==verify.length?0xc3:0xc2);part[1]=verify[1];System.arraycopy(verify,cursor,part,2,count);verifyParts.add(part);cursor+=count;}
        for(byte[] part:verifyParts){late.accept(part);late.accept(ack(0xd2,180,c180));late.accept(part);}
        check(late.stage==TransferSession.Stage.DONE&&late.activeVerified&&late.transferAccepted);
        // Fragmented inquiry with duplicate intermediate notifications.
        byte[] full=reply(Wire.DIAL,bytes(40,new byte[620]));List<byte[]> fragments=new ArrayList<>();fragments.add(Arrays.copyOfRange(full,0,240));int off=240;
        while(off<full.length){int count=Math.min(238,full.length-off);byte[] part=new byte[count+2];part[0]=(byte)(off+count==full.length?0xc3:0xc2);part[1]=full[1];System.arraycopy(full,off,part,2,count);fragments.add(part);off+=count;}
        Wire.Assembly assembly=new Wire.Assembly();boolean matched=false;for(byte[] part:fragments)for(int i=0;i<2;i++){byte[] p=assembly.feed(part);if(p!=null){check(Arrays.equals(full,p));matched=true;}}check(matched);
        // Optional private compiler samples validate the Android index parser.
        for(String filename:args)Wire.validateContainer(Files.readAllBytes(Path.of(filename)));
        System.out.println("PASS: container/CRC, preflight, no-overwrite, duplicate ACKs, transfer, fragmented metadata");
    }
}
