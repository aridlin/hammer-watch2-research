package local.hammer.installer;

import android.app.Activity;
import android.bluetooth.*;
import android.content.Intent;
import android.os.Build;
import android.test.InstrumentationTestCase;

/** Instrumentation APK only. Fixed Netsim address; refuse any non-emulator target. */
public class InstallerSmokeTest extends InstrumentationTestCase {
    public void testPackageTamperRejected() throws Exception {
        android.content.res.AssetManager assets=getInstrumentation().getTargetContext().getAssets();
        java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();
        try(java.util.zip.ZipInputStream input=new java.util.zip.ZipInputStream(assets.open("scifi-orange-pl-compass.hface"));java.util.zip.ZipOutputStream zip=new java.util.zip.ZipOutputStream(out)){
            java.util.zip.ZipEntry entry;
            while((entry=input.getNextEntry())!=null){byte[] bytes=FacePackage.bounded(input,1048576);if(entry.getName().equals("signature.bin"))bytes[0]^=1;
                zip.putNextEntry(new java.util.zip.ZipEntry(entry.getName()));zip.write(bytes);zip.closeEntry();}
        }
        try(java.io.InputStream key=assets.open("face-signing-public.der")){
            try{new FacePackage(new java.io.ByteArrayInputStream(out.toByteArray()),key);fail("Tampered signed package accepted");}
            catch(IllegalArgumentException expected){assertTrue(expected.getMessage().contains("signature"));}
        }
    }

    public void testSyntheticTransferOnly() throws Exception {
        String qemu=new java.io.BufferedReader(new java.io.InputStreamReader(
            Runtime.getRuntime().exec(new String[]{"/system/bin/getprop","ro.kernel.qemu"}).getInputStream())).readLine();
        assertEquals("Refuse physical Android devices","1",qemu);
        Intent intent=new Intent(getInstrumentation().getTargetContext(),MainActivity.class);intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        MainActivity activity=(MainActivity)getInstrumentation().startActivitySync(intent);
        long deadline=System.currentTimeMillis()+10000;
        while(activity.face==null&&System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertNotNull("Signed bundled face should import",activity.face);
        BluetoothManager manager=(BluetoothManager)activity.getSystemService(Activity.BLUETOOTH_SERVICE);
        BluetoothDevice peer=manager.getAdapter().getRemoteDevice("F2:F1:F0:00:00:04");
        getInstrumentation().runOnMainSync(()->activity.connectDevice(peer));
        deadline=System.currentTimeMillis()+25000;
        while(!activity.ready&&System.currentTimeMillis()<deadline)Thread.sleep(100);
        assertTrue("Synthetic service/MTU/CCCD setup should complete",activity.ready);
        java.util.List<String> observations=new java.util.concurrent.CopyOnWriteArrayList<>();
        getInstrumentation().runOnMainSync(()->{activity.testObserver=observations::add;activity.begin();});
        deadline=System.currentTimeMillis()+180000;
        while((activity.session==null||activity.busy())&&System.currentTimeMillis()<deadline)Thread.sleep(100);
        try(java.io.FileOutputStream out=new java.io.FileOutputStream(new java.io.File(activity.getFilesDir(),"synthetic-notifications.txt"))){
            for(String observation:observations)out.write((observation+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        }
        assertNotNull(activity.session);assertEquals("Installer status: "+activity.status.getText(),TransferSession.Stage.DONE,activity.session.stage);
        assertTrue("Receiver should confirm active synthetic face",activity.session.activeVerified);
        getInstrumentation().runOnMainSync(()->{activity.disconnect();activity.finish();});
    }
}
