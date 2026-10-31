package local.hammer.installer;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.spec.X509EncodedKeySpec;
import java.util.*;
import java.util.zip.*;
import org.json.JSONObject;

/** Bounded, signed local package. Vendor APKs, credentials and arbitrary files are not accepted. */
public final class FacePackage {
    public final byte[] data; public final String title,filename,status;
    public FacePackage(InputStream input,InputStream key) throws Exception {
        Map<String,byte[]> entries=new HashMap<>();int total=0;
        try(ZipInputStream zip=new ZipInputStream(input)){
            ZipEntry entry;while((entry=zip.getNextEntry())!=null){
                String name=entry.getName();int bound=name.equals("face.bin")?1048576:name.equals("manifest.json")?16384:name.equals("signature.bin")?512:0;
                if(bound==0||entry.isDirectory()||entries.containsKey(name))throw new IllegalArgumentException("Unexpected or duplicate package entry");
                byte[] value=bounded(zip,bound);total+=value.length;if(total>1066000)throw new IllegalArgumentException("Oversized package");entries.put(name,value);zip.closeEntry();
            }
        }
        if(entries.size()!=3)throw new IllegalArgumentException("Incomplete package");
        data=entries.get("face.bin");byte[] manifest=entries.get("manifest.json");
        PublicKey publicKey=KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(bounded(key,8192)));
        Signature verifier=Signature.getInstance("SHA256withRSA");verifier.initVerify(publicKey);verifier.update("HAMMER-FACE-PACKAGE-v1\0".getBytes(StandardCharsets.US_ASCII));verifier.update(java.nio.ByteBuffer.allocate(4).putInt(manifest.length).array());verifier.update(manifest);verifier.update(data);
        if(!verifier.verify(entries.get("signature.bin")))throw new IllegalArgumentException("Package signature does not match this installer");
        JSONObject meta=new JSONObject(new String(manifest,StandardCharsets.UTF_8));
        if(meta.getInt("schema")!=1||meta.getInt("device_model")!=2039||!meta.getString("firmware").equals("2.0.12")||meta.getInt("platform")!=3||meta.getInt("color")!=72||meta.getInt("framework")!=8||meta.getInt("compression")!=4)throw new IllegalArgumentException("Unsupported face compatibility profile");
        filename=Wire.validateContainer(data);if(!filename.equals(meta.getString("filename")))throw new IllegalArgumentException("Filename mismatch");
        if(TransferSession.canonical(filename).equals(TransferSession.canonical(meta.getString("origin_filename"))))throw new IllegalArgumentException("Factory filename replacement is forbidden");
        if(!hex(MessageDigest.getInstance("SHA-256").digest(data)).equals(meta.getString("sha256")))throw new IllegalArgumentException("Face hash mismatch");
        title=meta.getString("title");status=meta.getString("runtime_status");
        if(title.length()>100||status.length()>200)throw new IllegalArgumentException("Invalid package description");
        if(filename.startsWith("ewr24dig")||filename.startsWith("ewrcompass_24d"))throw new IllegalArgumentException("Earlier unstable test faces are not supported");
    }
    static byte[] bounded(InputStream in,int limit) throws IOException {
        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int size=0,count;
        while((count=in.read(buffer))!=-1){size+=count;if(size>limit)throw new IOException("Input exceeds limit");out.write(buffer,0,count);}return out.toByteArray();
    }
    static String hex(byte[] b){StringBuilder s=new StringBuilder();for(byte v:b)s.append(String.format(java.util.Locale.ROOT,"%02x",v&255));return s.toString();}
}
