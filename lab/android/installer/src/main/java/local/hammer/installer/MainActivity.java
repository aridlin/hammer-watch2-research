package local.hammer.installer;

import android.Manifest;
import android.app.*;
import android.bluetooth.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;

/** Local, foreground installer using the recovered face transfer only. */
public final class MainActivity extends Activity {
    static final UUID SERVICE=UUID.fromString("00000ff0-0000-1000-8000-00805f9b34fb"), WRITE=UUID.fromString("00000001-0000-1000-8000-00805f9b34fb"), NOTIFY=UUID.fromString("00000002-0000-1000-8000-00805f9b34fb"), CCCD=UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    final Handler main=new Handler(Looper.getMainLooper());
    TextView faceText,status;Button choose,connect,apply,recover;ProgressBar progress;
    FacePackage face;BluetoothGatt gatt;BluetoothGattCharacteristic write;
    TransferSession session;boolean ready=false,writing=false,loading=false,closed=false;
    int mtu=23;byte[] queued;Runnable deadline;
    java.util.function.Consumer<String> testObserver;

    @Override public void onCreate(Bundle b){super.onCreate(b);layout();
        try{getAssets().open("scifi-orange-pl-compass.hface").close();loadFace(null);}catch(IOException ignored){message("Import a prepared .hface package to begin.");}
    }
    void layout(){
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(dp(24),dp(30),dp(24),dp(20));root.setBackgroundColor(Color.rgb(19,20,23));
        ScrollView scroll=new ScrollView(this);scroll.addView(root);setContentView(scroll);
        TextView title=new TextView(this);title.setText(R.string.app_name);title.setTextSize(25);title.setTextColor(Color.rgb(246,127,49));root.addView(title);
        TextView intro=new TextView(this);intro.setText(R.string.intro);intro.setTextSize(16);intro.setPadding(0,dp(15),0,dp(24));root.addView(intro);
        faceText=new TextView(this);faceText.setText(R.string.no_face);faceText.setTextSize(18);faceText.setPadding(0,0,0,dp(18));root.addView(faceText);
        choose=button(root,"Import face",v->{if(busy())return;Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("*/*");startActivityForResult(intent,100);});
        connect=button(root,"Connect watch",v->{if(busy())return;if(gatt!=null){disconnect();message("Disconnected.");}else selectWatch();});
        apply=button(root,"Apply face",v->{if(face==null||!ready||busy())return;new AlertDialog.Builder(this).setTitle("Apply "+face.title+"?").setMessage("This is an experimental face, not yet validated on the watch. It is written as a separate entry; existing faces are kept. Keep this app open during transfer.").setNegativeButton("Cancel",null).setPositiveButton("Apply",(dialog,which)->begin()).show();});
        recover=button(root,"Recover interrupted transfer",v->{if(face==null||!ready||busy())return;new AlertDialog.Builder(this).setTitle("Recover interrupted transfer?").setMessage("Continue the existing transfer only if the watch returns a saved position and checksum matching this face. No overwrite or delete command is sent.").setNegativeButton("Cancel",null).setPositiveButton("Recover",(dialog,which)->beginRecovery()).show();});
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setMax(100);root.addView(progress,new LinearLayout.LayoutParams(-1,dp(16)));
        status=new TextView(this);status.setTextSize(16);status.setPadding(0,dp(20),0,0);root.addView(status);refresh();
    }
    Button button(LinearLayout root,String text,View.OnClickListener click){Button b=new Button(this);b.setText(text);b.setOnClickListener(click);root.addView(b,new LinearLayout.LayoutParams(-1,dp(56)));return b;}
    int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
    boolean busy(){return session!=null&&session.stage!=TransferSession.Stage.DONE&&session.stage!=TransferSession.Stage.FAILED;}
    void refresh(){if(apply==null)return;choose.setEnabled(!busy()&&!loading);connect.setEnabled(!busy()&&!loading);connect.setText(gatt==null?"Connect watch":"Disconnect");apply.setEnabled(face!=null&&ready&&!busy()&&!loading);if(recover!=null)recover.setEnabled(face!=null&&ready&&!busy()&&!loading);}
    void message(String s){status.setText(s);refresh();}
    void loadFace(Uri uri){if(busy())return;loading=true;refresh();new Thread(()->{
        try(InputStream in=uri==null?getAssets().open("scifi-orange-pl-compass.hface"):getContentResolver().openInputStream(uri);InputStream key=getAssets().open("face-signing-public.der")){
            if(in==null)throw new IOException("Could not open package");FacePackage loaded=new FacePackage(in,key);
            main.post(()->{if(closed)return;face=loaded;loading=false;faceText.setText(getString(R.string.face_description,face.title,face.status));progress.setProgress(0);message("Face verified locally. Connect your watch to continue.");});
        }catch(Exception error){main.post(()->{if(closed)return;loading=false;message("Cannot import this face: "+safe(error));});}
    },"face-import").start();}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==100&&result==RESULT_OK&&data!=null&&data.getData()!=null)loadFace(data.getData());}
    String safe(Throwable error){if(error instanceof IllegalArgumentException||error instanceof IOException){String text=error.getMessage();if(text!=null&&text.length()<180)return text;}return "Invalid package or unavailable Bluetooth operation";}
    void selectWatch(){
        if(Build.VERSION.SDK_INT>=31&&checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT},101);return;}
        try{
            BluetoothManager manager=(BluetoothManager)getSystemService(BLUETOOTH_SERVICE);BluetoothAdapter adapter=manager.getAdapter();
            if(adapter==null||!adapter.isEnabled()){message("Enable Bluetooth in Android settings first.");startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS));return;}
            List<BluetoothDevice> devices=new ArrayList<>();List<String> names=new ArrayList<>();
            for(BluetoothDevice device:adapter.getBondedDevices()){String name=device.getName();if(name!=null&&(name.toUpperCase(Locale.ROOT).contains("HW2")||name.toUpperCase(Locale.ROOT).contains("HAMMER"))){devices.add(device);names.add(name);}}
            if(devices.isEmpty()){new AlertDialog.Builder(this).setTitle("Pair the watch first").setMessage("Pair HW2 in Android Bluetooth settings. Return here afterward. This installer does not reset or unbind the watch.").setPositiveButton("Bluetooth settings",(d,w)->startActivity(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS))).setNegativeButton("Cancel",null).show();return;}
            new AlertDialog.Builder(this).setTitle("Choose your watch").setItems(names.toArray(new String[0]),(d,w)->connectDevice(devices.get(w))).show();
        }catch(RuntimeException error){message("Bluetooth is unavailable: "+safe(error));}
    }
    @Override public void onRequestPermissionsResult(int r,String[] p,int[] grants){super.onRequestPermissionsResult(r,p,grants);if(r==101&&grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED)selectWatch();else message("Nearby-device permission is required to connect.");}
    void connectDevice(BluetoothDevice device){disconnect();message("Connecting…");try{gatt=device.connectGatt(this,false,callbacks,BluetoothDevice.TRANSPORT_LE);refresh();timeout("Connection timed out",20000);}catch(SecurityException e){fail("Nearby-device permission is required");}catch(RuntimeException e){fail("Could not connect");}}
    void timeout(String text,int ms){cancelDeadline();deadline=()->fail(text);main.postDelayed(deadline,ms);}
    void cancelDeadline(){if(deadline!=null)main.removeCallbacks(deadline);deadline=null;}
    void begin(){begin(false);}
    void beginRecovery(){begin(true);}
    void begin(boolean recovery){try{session=new TransferSession(face.data,face.filename,mtu,recovery);progress.setProgress(0);getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);message(recovery?"Checking the interrupted transfer…":"Checking watch compatibility and free space…");send(session.first());}catch(RuntimeException e){fail(safe(e));}}
    void send(byte[] bytes){if(bytes==null)return;if(writing){if(queued!=null){fail("Bluetooth write queue conflict");return;}queued=bytes;timeout("Bluetooth write completion timed out",12000);return;}
        if(gatt==null||write==null||bytes.length>mtu-3){fail("Bluetooth connection is not ready");return;}
        try{writing=true;write.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);write.setValue(bytes);if(!gatt.writeCharacteristic(write)){writing=false;fail("Bluetooth refused the write; no retry was sent");return;}timeout("Watch response timed out; transfer stopped without retry",12000);}catch(SecurityException e){writing=false;fail("Nearby-device permission was revoked");}catch(RuntimeException e){writing=false;fail("Bluetooth write failed; transfer stopped");}
    }
    void received(BluetoothGatt from,byte[] bytes){if(from!=gatt||session==null||!busy())return;
        try{if((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0&&testObserver!=null)testObserver.accept(session.stage.name()+":"+FacePackage.hex(bytes));byte[] next=session.accept(bytes);
            if(next!=null){cancelDeadline();send(next);}
            progress.setProgress((int)(100L*session.offset/session.data.length));
            if(session.stage==TransferSession.Stage.DATA||session.stage==TransferSession.Stage.END)message("Applying face… "+progress.getProgress()+"%");
            if(session.stage==TransferSession.Stage.VERIFY)message("Transfer accepted. Checking the face list…");
            if(session.stage==TransferSession.Stage.DONE){cancelDeadline();getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);progress.setProgress(100);message(session.alreadyActive?"The watch already reports this face active. No transfer was sent. Check its display.":session.activeVerified?"Face applied and reported active. Check its appearance and behavior on the watch.":"Transfer accepted. Select the new face on the watch if needed; active selection was not confirmed.");}
        }catch(RuntimeException e){fail(safe(e));}
    }
    void fail(String reason){boolean accepted=session!=null&&session.transferAccepted;
        if(session!=null)session.abort();cancelDeadline();queued=null;writing=false;getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        message(accepted?"Transfer was accepted, but final face selection could not be verified. Check the watch.":reason+". No automatic retry was sent.");disconnect();}
    void disconnect(){cancelDeadline();ready=false;write=null;queued=null;writing=false;if(session!=null&&busy())session.abort();BluetoothGatt old=gatt;gatt=null;if(old!=null){try{old.disconnect();old.close();}catch(SecurityException ignored){}catch(RuntimeException ignored){}}refresh();}
    final BluetoothGattCallback callbacks=new BluetoothGattCallback(){
        @Override public void onConnectionStateChange(BluetoothGatt from,int result,int state){main.post(()->{if(from!=gatt)return;if(result!=BluetoothGatt.GATT_SUCCESS||state==BluetoothProfile.STATE_DISCONNECTED){fail("Watch disconnected");return;}if(state==BluetoothProfile.STATE_CONNECTED){cancelDeadline();try{if(!from.requestMtu(247)){fail("Could not request Bluetooth MTU");return;}timeout("Bluetooth MTU negotiation timed out",15000);}catch(SecurityException e){fail("Nearby-device permission was revoked");}}});}
        @Override public void onMtuChanged(BluetoothGatt from,int negotiated,int result){main.post(()->{if(from!=gatt)return;if(result!=0||negotiated<43){fail("Bluetooth MTU unsupported");return;}mtu=negotiated;cancelDeadline();try{if(!from.discoverServices()){fail("Service discovery failed");return;}timeout("Service discovery timed out",15000);}catch(SecurityException e){fail("Nearby-device permission was revoked");}});}
        @Override public void onServicesDiscovered(BluetoothGatt from,int result){main.post(()->{if(from!=gatt)return;try{if(result!=0)throw new IllegalArgumentException("Service discovery failed");BluetoothGattService service=from.getService(SERVICE);if(service==null)throw new IllegalArgumentException("HAMMER face service not found");write=service.getCharacteristic(WRITE);BluetoothGattCharacteristic notify=service.getCharacteristic(NOTIFY);if(write==null||notify==null||!from.setCharacteristicNotification(notify,true))throw new IllegalArgumentException("Required Bluetooth characteristics unavailable");BluetoothGattDescriptor descriptor=notify.getDescriptor(CCCD);if(descriptor==null)throw new IllegalArgumentException("Notification descriptor unavailable");descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);if(!from.writeDescriptor(descriptor))throw new IllegalArgumentException("Cannot enable notifications");timeout("Notification setup timed out",15000);}catch(SecurityException e){fail("Nearby-device permission was revoked");}catch(RuntimeException e){fail(safe(e));}});}
        @Override public void onDescriptorWrite(BluetoothGatt from,BluetoothGattDescriptor descriptor,int result){main.post(()->{if(from!=gatt)return;if(result!=0){fail("Notification setup failed");return;}cancelDeadline();ready=true;message("Watch connected. Apply runs fresh compatibility checks before writing the face.");});}
        @Override public void onCharacteristicChanged(BluetoothGatt from,BluetoothGattCharacteristic characteristic){if(NOTIFY.equals(characteristic.getUuid())){byte[] value=characteristic.getValue();if(value!=null){byte[] copy=value.clone();main.post(()->received(from,copy));}}}
        @Override public void onCharacteristicChanged(BluetoothGatt from,BluetoothGattCharacteristic characteristic,byte[] value){if(NOTIFY.equals(characteristic.getUuid())){byte[] copy=value.clone();main.post(()->received(from,copy));}}
        @Override public void onCharacteristicWrite(BluetoothGatt from,BluetoothGattCharacteristic characteristic,int result){main.post(()->{if(from!=gatt)return;writing=false;if(result!=0){fail("Bluetooth write was not accepted");return;}if(queued!=null){byte[] next=queued;queued=null;send(next);}});}
    };
    @Override public void onBackPressed(){if(busy()){new AlertDialog.Builder(this).setTitle("Stop transfer?").setMessage("A partially received face may remain on the watch. No reset or delete command will be sent.").setNegativeButton("Keep transferring",null).setPositiveButton("Stop",(d,w)->{disconnect();message("Transfer stopped. Check watch faces before retrying.");}).show();}else super.onBackPressed();}
    @Override protected void onDestroy(){closed=true;disconnect();super.onDestroy();}
}
