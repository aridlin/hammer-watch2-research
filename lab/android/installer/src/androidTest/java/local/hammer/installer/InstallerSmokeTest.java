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

    public void testSyntheticTransferOnly() throws Exception {runTransfer(false);}
    public void testResumeSyntheticTransfer() throws Exception {runTransfer(true);}
    void runTransfer(boolean recovery) throws Exception {
        String qemu=new java.io.BufferedReader(new java.io.InputStreamReader(
            Runtime.getRuntime().exec(new String[]{"/system/bin/getprop","ro.kernel.qemu"}).getInputStream())).readLine();
        assertEquals("Refuse physical Android devices","1",qemu);
        Intent intent=new Intent(getInstrumentation().getTargetContext(),MainActivity.class);intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        MainActivity activity=(MainActivity)getInstrumentation().startActivitySync(intent);
        getInstrumentation().runOnMainSync(()->activity.setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT));
        long orientDeadline=System.currentTimeMillis()+3000;
        while(activity.getResources().getConfiguration().orientation!=android.content.res.Configuration.ORIENTATION_PORTRAIT&&System.currentTimeMillis()<orientDeadline)Thread.sleep(50);
        assertEquals(android.content.res.Configuration.ORIENTATION_PORTRAIT,activity.getResources().getConfiguration().orientation);
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
        getInstrumentation().runOnMainSync(()->{activity.testObserver=observations::add;if(recovery)activity.beginRecovery();else activity.begin();});
        deadline=System.currentTimeMillis()+180000;
        boolean rotated=false;
        while((activity.session==null||activity.busy())&&System.currentTimeMillis()<deadline){
            if(!rotated&&activity.session!=null&&activity.session.offset>activity.session.data.length/3&&activity.busy()){
                getInstrumentation().runOnMainSync(()->activity.setRequestedOrientation(android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE));
                rotated=true;
            }
            Thread.sleep(100);
        }
        if(!recovery||activity.session.resumedFrom<activity.session.data.length)assertTrue("Rotation should occur during transfer",rotated);
        getInstrumentation().waitForIdleSync();
        assertFalse("Screen rotation must not destroy the transferring activity",activity.closed);
        if(rotated)assertEquals(android.content.res.Configuration.ORIENTATION_LANDSCAPE,activity.getResources().getConfiguration().orientation);
        try(java.io.FileOutputStream out=new java.io.FileOutputStream(new java.io.File(activity.getFilesDir(),"synthetic-notifications.txt"))){
            for(String observation:observations)out.write((observation+"\n").getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        }
        assertNotNull(activity.session);assertEquals("Installer status: "+activity.status.getText(),TransferSession.Stage.DONE,activity.session.stage);
        assertTrue("Receiver should confirm active synthetic face",activity.session.activeVerified);
        if(recovery)assertTrue("A saved position must be verified",activity.session.resumedFrom>0);
        getInstrumentation().runOnMainSync(()->{activity.disconnect();activity.finish();});
    }
}
