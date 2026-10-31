package local.hammer.installer;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.CRC32;

/** Fixed recovered face/inquiry protocol. No binding, delete, activation or OTA. */
public final class Wire {
    public static final byte[] DEVICE=hex("c10a010100010b000000000000"), DIAL=hex("c13c010100160d000000000800"), MTU=hex("c11e010100220d000000000801");
    public static int u8(byte b){return b&255;}
    public static int u16(byte[] b,int p){need(b,p,2);return u8(b[p])|(u8(b[p+1])<<8);}
    public static long u32(byte[] b,int p){need(b,p,4);return (long)u8(b[p])|((long)u8(b[p+1])<<8)|((long)u8(b[p+2])<<16)|((long)u8(b[p+3])<<24);}
    static void need(byte[] b,int p,int n){if(p<0||n<0||p>b.length-n)throw new IllegalArgumentException("Truncated data");}
    public static byte[] hex(String s){byte[] b=new byte[s.length()/2];for(int i=0;i<b.length;i++)b[i]=(byte)Integer.parseInt(s.substring(i*2,i*2+2),16);return b;}
    public static void put32(byte[] b,int p,long n){for(int i=0;i<4;i++)b[p+i]=(byte)(n>>>(i*8));}
    public static int crc16(byte[] b,int offset,int count,int crc){need(b,offset,count);for(int p=offset;p<offset+count;p++){crc^=u8(b[p])<<8;for(int i=0;i<8;i++)crc=((crc&0x8000)!=0?(crc<<1)^0x1021:crc<<1)&65535;}return crc;}
    public static String ascii(byte[] b,int offset,int count){need(b,offset,count);int end=offset;while(end<offset+count&&b[end]!=0)end++;return new String(b,offset,end-offset,StandardCharsets.US_ASCII);}
    public static String validateContainer(byte[] b){
        if(b.length<44||b.length>1048576)throw new IllegalArgumentException("Face size is unsupported");
        CRC32 crc=new CRC32();crc.update(b,44,b.length-44);
        if(crc.getValue()!=u32(b,40)||u8(b[39])!=4||u32(b,30)!=0x5aa54321L)throw new IllegalArgumentException("Invalid face header or checksum");
        int n=u16(b,37),end=44+n*38;if(n<1||n>4096||end>b.length)throw new IllegalArgumentException("Invalid face index");
        List<long[]> ranges=new ArrayList<>();Set<String> names=new HashSet<>();
        for(int i=0;i<n;i++){
            int p=44+i*38;String name=ascii(b,p,30);long offset=u32(b,p+30),size=u32(b,p+34);
            if(name.isEmpty()||!names.add(name)||offset<end||offset+size>b.length)throw new IllegalArgumentException("Invalid resource index");
            if(size>0)ranges.add(new long[]{offset,offset+size});
        }
        ranges.sort(Comparator.comparingLong(x->x[0]));for(int i=1;i<ranges.size();i++)if(ranges.get(i)[0]<ranges.get(i-1)[1])throw new IllegalArgumentException("Overlapping resources");
        String name=ascii(b,0,30);if(!name.matches("[A-Za-z0-9_@-]{1,29}"))throw new IllegalArgumentException("Unsupported face name");return name+".bin";
    }
    public static byte[] start(byte[] data,String filename){byte[] name=(filename+"\0").getBytes(StandardCharsets.US_ASCII);byte[] p=new byte[11+name.length];p[0]=(byte)0xd1;put32(p,2,data.length);put32(p,6,data.length);p[10]=1;System.arraycopy(name,0,p,11,name.length);return p;}
    public static byte[] block(byte[] data,int offset,int size){need(data,offset,size);byte[] p=new byte[size+2];p[0]=(byte)0xd2;System.arraycopy(data,offset,p,2,size);return p;}
    public static byte[] end(int crc){byte[] p=new byte[7];p[0]=(byte)0xd4;put32(p,3,crc);return p;}
    public static void ack(byte[] p,int opcode,boolean block,int offset,int crc){
        if((p.length!=3&&p.length!=7&&p.length!=11)||u8(p[0])!=opcode||p[2]!=0)throw new IllegalArgumentException("Watch rejected the transfer");
        if(block&&(p.length!=11||u32(p,3)!=offset||u32(p,7)!=crc))throw new IllegalArgumentException("Transfer offset/checksum mismatch");
    }
    /** Both raw and adjacent-duplicate-suppressed paths; accept CRC-valid only. */
    public static final class Assembly {
        byte[] raw,filtered,previous;
        byte[] step(byte[] pending,byte[] value){
            if(value.length<2||value.length>514)return null;
            int kind=u8(value[0]);
            if(kind==0xc1){if(value.length<11)return null;pending=value.clone();}
            else if(kind==0xc2||kind==0xc3){if(pending==null||(pending[1]&127)!=(value[1]&127))return null;byte[] next=Arrays.copyOf(pending,pending.length+value.length-2);System.arraycopy(value,2,next,pending.length,value.length-2);pending=next;}
            else return pending;
            long length=u32(pending,6)+2;if(length<13||length>4098||pending.length>length)return null;return pending;
        }
        boolean complete(byte[] p){return p!=null&&p.length==u32(p,6)+2&&crc16(p,0,p.length-2,65535)==u16(p,p.length-2);}
        public byte[] feed(byte[] value){raw=step(raw,value);if(!Arrays.equals(previous,value))filtered=step(filtered,value);previous=value.clone();
            byte[] a=complete(raw)?raw:null,b=complete(filtered)?filtered:null;
            if(a!=null&&b!=null&&!Arrays.equals(a,b))throw new IllegalArgumentException("Ambiguous inquiry reply");
            byte[] result=a!=null?a:b;if(result!=null){raw=null;filtered=null;}return result;}
    }
    public static byte[] body(byte[] reply,byte[] request){
        if(reply.length<13||(reply[1]&127)!=(request[1]&127)||reply[4]!=request[4]||reply[5]!=request[5]||reply[10]!=0||(reply[1]&128)==0||u32(reply,6)+2!=reply.length||crc16(reply,0,reply.length-2,65535)!=u16(reply,reply.length-2))throw new IllegalArgumentException("Invalid watch inquiry response");
        return Arrays.copyOfRange(reply,11,reply.length-2);
    }
    public static final class Proto {
        final Map<Integer,List<Object>> fields=new HashMap<>();
        public Proto(byte[] data){if(data.length>4096)throw new IllegalArgumentException("Oversized metadata");int[] p={0};while(p[0]<data.length){long tag=varint(data,p);int field=(int)(tag>>>3),wire=(int)(tag&7);if(field<1)throw new IllegalArgumentException("Invalid protobuf field");Object value;
            if(wire==0)value=varint(data,p);
            else if(wire==2){long length=varint(data,p);if(length>4096)throw new IllegalArgumentException("Oversized field");need(data,p[0],(int)length);value=Arrays.copyOfRange(data,p[0],p[0]+(int)length);p[0]+=(int)length;}
            else if(wire==1||wire==5){int length=wire==1?8:4;need(data,p[0],length);p[0]+=length;continue;}
            else throw new IllegalArgumentException("Unsupported metadata wire type");
            fields.computeIfAbsent(field,k->new ArrayList<>()).add(value);
        }}
        static long varint(byte[] b,int[] p){long n=0;for(int shift=0;shift<63;shift+=7){need(b,p[0],1);int v=u8(b[p[0]++]);n|=(long)(v&127)<<shift;if((v&128)==0)return n;}throw new IllegalArgumentException("Invalid varint");}
        public long number(int field){List<Object> l=fields.get(field);return l==null?0:l.get(0) instanceof Long?(Long)l.get(0):failNumber();}
        long failNumber(){throw new IllegalArgumentException("Invalid numeric field");}
        public List<byte[]> bytes(int field){List<byte[]> out=new ArrayList<>();for(Object o:fields.getOrDefault(field,Collections.emptyList())){if(!(o instanceof byte[]))throw new IllegalArgumentException("Invalid bytes field");out.add((byte[])o);}return out;}
        public String text(int field){List<byte[]> b=bytes(field);return b.isEmpty()?"":new String(b.get(0),StandardCharsets.UTF_8);}
    }
}
