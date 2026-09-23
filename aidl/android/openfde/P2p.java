/**
 * Copyright (C) 2021 The OpenFDE Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package android.openfde;

import android.content.Context;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;

import java.lang.reflect.Method;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;



public class P2p {
    private static final String TAG = "fdep2p";
    public static final String SERVICE_NAME = "openfdep2p";
    public static final String NETWORK_SERVICE_NAME = "openfdep2pnetwork";

    private static IP2p sService;
    private static ISupplicantP2pNetwork sNetworkService;
    private static P2p sInstance;
    private final Context mContext;
    private EventListener eventListener;
    private IP2pCallback callback;

    /**
     * Listener for P2P events reported by the openfdep2p binder service.
     * All methods have empty default implementations, override only the
     * events you need. Callbacks arrive on a binder thread.
     */
    public interface EventListener {
        default void onEvents(int what, String data) {
        }

        default void onDeviceFound(byte[] srcAddress, byte[] p2pDeviceAddress,
                byte[] primaryDeviceType, String deviceName, int configMethods,
                int deviceCapabilities, int groupCapabilities, byte[] wfdDeviceInfo) {
        }

        default void onDeviceLost(byte[] p2pDeviceAddress) {
        }

        default void onFindStopped() {
        }

        default void onGoNegotiationCompleted(int status) {
        }

        default void onGoNegotiationRequest(byte[] srcAddress, int passwordId) {
        }

        default void onGroupFormationFailure(String failureReason) {
        }

        default void onGroupFormationSuccess() {
        }

        default void onGroupRemoved(String groupIfname, boolean isGroupOwner) {
        }

        default void onGroupStarted(String groupIfname, boolean isGroupOwner, byte[] ssid,
                int frequency, byte[] psk, String passphrase, byte[] goDeviceAddress,
                boolean isPersistent) {
        }

        default void onInvitationReceived(byte[] srcAddress, byte[] goDeviceAddress,
                byte[] bssid, int persistentNetworkId, int operatingFrequency) {
        }

        default void onInvitationResult(byte[] bssid, int status) {
        }

        default void onProvisionDiscoveryCompleted(byte[] p2pDeviceAddress, boolean isRequest,
                int status, int configMethods, String generatedPin) {
        }

        default void onR2DeviceFound(byte[] srcAddress, byte[] p2pDeviceAddress,
                byte[] primaryDeviceType, String deviceName, int configMethods,
                int deviceCapabilities, int groupCapabilities,
                byte[] wfdDeviceInfo, byte[] wfdR2DeviceInfo) {
        }

        default void onServiceDiscoveryResponse(byte[] srcAddress, int updateIndicator,
                byte[] tlvs) {
        }

        default void onStaAuthorized(byte[] srcAddress, byte[] p2pDeviceAddress) {
        }

        default void onStaDeauthorized(byte[] srcAddress, byte[] p2pDeviceAddress) {
        }

        default void onGroupFrequencyChanged(String groupIfname, int frequency) {
        }

        default void onDeviceFoundWithVendorElements(byte[] srcAddress, byte[] p2pDeviceAddress,
                byte[] primaryDeviceType, String deviceName, int configMethods,
                int deviceCapabilities, int groupCapabilities,
                byte[] wfdDeviceInfo, byte[] wfdR2DeviceInfo, byte[] vendorElemBytes) {
        }

        default void onGroupStartedWithParams(String groupInterfaceName, boolean isGroupOwner,
                byte[] ssid, int frequencyMHz, byte[] psk, String passphrase,
                byte[] goDeviceAddress, boolean isPersistent) {
        }

        default void onPeerClientJoined(byte[] srcAddress, byte[] p2pDeviceAddress,
                boolean isVpSupported) {
        }

        default void onPeerClientDisconnected(byte[] srcAddress, byte[] p2pDeviceAddress) {
        }

        default void onProvisionDiscoveryCompletedEvent(byte[] p2pDeviceAddress, int status,
                int configMethods, String generatedPin) {
        }

        default void onDeviceFoundWithParams(byte[] srcAddress, byte[] p2pDeviceAddress,
                byte[] primaryDeviceType, String deviceName, int configMethods,
                int deviceCapabilities, int groupCapabilities, byte[] wfdDeviceInfo,
                byte[] wfdR2DeviceInfo, byte[] vendorElem) {
        }

        default void onGoNegotiationRequestWithParams(byte[] srcAddress, int passwordId,
                int goIntent) {
        }

        default void onInvitationReceivedWithParams(byte[] srcAddress, byte[] goDeviceAddress,
                byte[] bssid, int persistentNetworkId, int operatingFrequencyMHz) {
        }

        default void onUsdBasedServiceDiscoveryResult(int sessionId, byte[] srcAddress,
                int updateIndicator, byte[] tlvs) {
        }

        default void onUsdBasedServiceDiscoveryTerminated(int sessionId, int reasonCode) {
        }

        default void onUsdBasedServiceAdvertisementTerminated(int sessionId, int reasonCode) {
        }
    }

    private P2p(Context context) {
        mContext = context == null ? null : context.getApplicationContext();
        sService = getService();
    }

    public static P2p getInstance(Context context) {
        if (sInstance == null) {
            sInstance = new P2p(context);
        }
        return sInstance;
    }

    public static IP2p getService() {
        if (sService != null) {
            return sService;
        }
        try {
            Class<?> serviceManager = Class.forName("android.os.ServiceManager");
            Method getServiceMethod = serviceManager.getDeclaredMethod("getService", String.class);
            IBinder b = (IBinder) getServiceMethod.invoke(null, SERVICE_NAME);
            if (b == null) {
                Log.e(TAG, SERVICE_NAME + " null SAD!");
                return null;
            }
            sService = IP2p.Stub.asInterface(b);
        } catch (Exception e) {
            Log.e(TAG, "Error getting service via reflection", e);
            return null;
        }
        return sService;
    }

    public static ISupplicantP2pNetwork getNetworkService() {
        if (sNetworkService != null) {
            return sNetworkService;
        }
        try {
            Class<?> serviceManager = Class.forName("android.os.ServiceManager");
            Method getServiceMethod = serviceManager.getDeclaredMethod("getService", String.class);
            IBinder b = (IBinder) getServiceMethod.invoke(null, NETWORK_SERVICE_NAME);
            if (b == null) {
                Log.e(TAG, NETWORK_SERVICE_NAME + " null SAD!");
                return null;
            }
            sNetworkService = ISupplicantP2pNetwork.Stub.asInterface(b);
        } catch (Exception e) {
            Log.e(TAG, "Error getting P2P network service via reflection", e);
            return null;
        }
        return sNetworkService;
    }

    public boolean addBonjourService(byte[] query, byte[] response) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.addBonjourService(query, response);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean addGroup(boolean persistent, int persistentNetworkId) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.addGroup(persistent, persistentNetworkId);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean cancelConnect() {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.cancelConnect();
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pStopFind() {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_stop_find();
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pAspProvision(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_asp_provision(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pAspProvisionResp(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_asp_provision_resp(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pConnect(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_connect(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pListen(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_listen(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pGroupRemove(String ifname) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_group_remove(ifname);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pGroupMember(String ifname) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_group_member(ifname);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pProvDisc(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_prov_disc(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public String p2pGetPassphrase() {
        IP2p service = getService();
        if (service == null) {
            return "";
        }
        try {
            return service.p2p_get_passphrase();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public String p2pServDiscReq(String args) {
        IP2p service = getService();
        if (service == null) {
            return "";
        }
        try {
            return service.p2p_serv_disc_req(args);
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public boolean p2pServDiscCancel(String identifier) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_serv_disc_cancel(identifier);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pServDiscResp(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_serv_disc_resp(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pServiceUpdate() {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_service_update();
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pServDiscExternal(String value) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_serv_disc_external(value);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pServiceFlush() {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_service_flush();
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pServiceRep(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_service_rep(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pServiceDel(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_service_del(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pReject(String peer) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_reject(peer);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pInvite(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_invite(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public String p2pPeers() {
        IP2p service = getService();
        if (service == null) {
            return "";
        }
        try {
            return service.p2p_peers();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public String p2pPeer(String peer) {
        IP2p service = getService();
        if (service == null) {
            return "";
        }
        try {
            return service.p2p_peer(peer);
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public boolean p2pSet(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_set(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pFlush() {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_flush();
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pUnauthorize(String peer) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_unauthorize(peer);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pPresenceReq(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_presence_req(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pExtListen(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_ext_listen(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pRemoveClient(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_remove_client(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean p2pFind(String args) {
        IP2p service = getService();
        if (service == null) {
            return false;
        }
        try {
            service.p2p_find(args);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    private void dispatchP2pEvent(int what, String data) {
        EventListener listener = eventListener;
        if (listener == null) {
            return;
        }
        listener.onEvents(what, data);
        try {
            JSONObject event = new JSONObject(data == null ? "{}" : data);
            String name = event.optString("event", "");
            JSONArray args = event.optJSONArray("args");
            if (args == null) {
                args = new JSONArray();
            }
            switch (name) {
                case "onDeviceFound":
                    listener.onDeviceFound(bytesArg(args, 0), bytesArg(args, 1), bytesArg(args, 2),
                            stringArg(args, 3), intArg(args, 4), intArg(args, 5), intArg(args, 6),
                            bytesArg(args, 7));
                    break;
                case "onDeviceLost":
                    listener.onDeviceLost(bytesArg(args, 0));
                    break;
                case "onFindStopped":
                    listener.onFindStopped();
                    break;
                case "onGoNegotiationCompleted":
                    listener.onGoNegotiationCompleted(intArg(args, 0));
                    break;
                case "onGoNegotiationRequest":
                    listener.onGoNegotiationRequest(bytesArg(args, 0), intArg(args, 1));
                    break;
                case "onGroupFormationFailure":
                    listener.onGroupFormationFailure(stringArg(args, 0));
                    break;
                case "onGroupFormationSuccess":
                    listener.onGroupFormationSuccess();
                    break;
                case "onGroupRemoved":
                    listener.onGroupRemoved(stringArg(args, 0), boolArg(args, 1));
                    break;
                case "onGroupStarted":
                    listener.onGroupStarted(stringArg(args, 0), boolArg(args, 1), bytesArg(args, 2),
                            intArg(args, 3), bytesArg(args, 4), stringArg(args, 5),
                            bytesArg(args, 6), boolArg(args, 7));
                    break;
                case "onInvitationReceived":
                    listener.onInvitationReceived(bytesArg(args, 0), bytesArg(args, 1),
                            bytesArg(args, 2), intArg(args, 3), intArg(args, 4));
                    break;
                case "onInvitationResult":
                    listener.onInvitationResult(bytesArg(args, 0), intArg(args, 1));
                    break;
                case "onProvisionDiscoveryCompleted":
                    listener.onProvisionDiscoveryCompleted(bytesArg(args, 0), boolArg(args, 1),
                            intArg(args, 2), intArg(args, 3), stringArg(args, 4));
                    break;
                case "onR2DeviceFound":
                    listener.onR2DeviceFound(bytesArg(args, 0), bytesArg(args, 1), bytesArg(args, 2),
                            stringArg(args, 3), intArg(args, 4), intArg(args, 5), intArg(args, 6),
                            bytesArg(args, 7), bytesArg(args, 8));
                    break;
                case "onServiceDiscoveryResponse":
                    listener.onServiceDiscoveryResponse(bytesArg(args, 0), intArg(args, 1),
                            bytesArg(args, 2));
                    break;
                case "onStaAuthorized":
                    listener.onStaAuthorized(bytesArg(args, 0), bytesArg(args, 1));
                    break;
                case "onStaDeauthorized":
                    listener.onStaDeauthorized(bytesArg(args, 0), bytesArg(args, 1));
                    break;
                case "onGroupFrequencyChanged":
                    listener.onGroupFrequencyChanged(stringArg(args, 0), intArg(args, 1));
                    break;
                case "onDeviceFoundWithVendorElements":
                    listener.onDeviceFoundWithVendorElements(bytesArg(args, 0), bytesArg(args, 1),
                            bytesArg(args, 2), stringArg(args, 3), intArg(args, 4), intArg(args, 5),
                            intArg(args, 6), bytesArg(args, 7), bytesArg(args, 8), bytesArg(args, 9));
                    break;
                case "onGroupStartedWithParams":
                    listener.onGroupStartedWithParams(stringArg(args, 0), boolArg(args, 1),
                            bytesArg(args, 2), intArg(args, 3), bytesArg(args, 4), stringArg(args, 5),
                            bytesArg(args, 6), boolArg(args, 7));
                    break;
                case "onPeerClientJoined":
                    listener.onPeerClientJoined(bytesArg(args, 0), bytesArg(args, 1), boolArg(args, 2));
                    break;
                case "onPeerClientDisconnected":
                    listener.onPeerClientDisconnected(bytesArg(args, 0), bytesArg(args, 1));
                    break;
                case "onProvisionDiscoveryCompletedEvent":
                    listener.onProvisionDiscoveryCompletedEvent(bytesArg(args, 0), intArg(args, 1),
                            intArg(args, 2), stringArg(args, 3));
                    break;
                case "onDeviceFoundWithParams":
                    listener.onDeviceFoundWithParams(bytesArg(args, 0), bytesArg(args, 1),
                            bytesArg(args, 2), stringArg(args, 3), intArg(args, 4), intArg(args, 5),
                            intArg(args, 6), bytesArg(args, 7), bytesArg(args, 8), bytesArg(args, 9));
                    break;
                case "onGoNegotiationRequestWithParams":
                    listener.onGoNegotiationRequestWithParams(bytesArg(args, 0), intArg(args, 1),
                            intArg(args, 2));
                    break;
                case "onInvitationReceivedWithParams":
                    listener.onInvitationReceivedWithParams(bytesArg(args, 0), bytesArg(args, 1),
                            bytesArg(args, 2), intArg(args, 3), intArg(args, 4));
                    break;
                case "onUsdBasedServiceDiscoveryResult":
                    listener.onUsdBasedServiceDiscoveryResult(intArg(args, 0), bytesArg(args, 1),
                            intArg(args, 2), bytesArg(args, 3));
                    break;
                case "onUsdBasedServiceDiscoveryTerminated":
                    listener.onUsdBasedServiceDiscoveryTerminated(intArg(args, 0), intArg(args, 1));
                    break;
                case "onUsdBasedServiceAdvertisementTerminated":
                    listener.onUsdBasedServiceAdvertisementTerminated(intArg(args, 0), intArg(args, 1));
                    break;
                default:
                    Log.w(TAG, "Unknown P2P event " + name + " (" + what + ")");
                    break;
            }
        } catch (JSONException | IllegalArgumentException e) {
            Log.e(TAG, "Failed to dispatch P2P event: " + data, e);
        }
    }

    private static String stringArg(JSONArray args, int index) throws JSONException {
        return index < args.length() ? args.optString(index, "") : "";
    }

    private static int intArg(JSONArray args, int index) throws JSONException {
        String value = stringArg(args, index);
        if (value.isEmpty()) {
            return 0;
        }
        return Integer.parseInt(value);
    }

    private static boolean boolArg(JSONArray args, int index) throws JSONException {
        return Boolean.parseBoolean(stringArg(args, index));
    }

    private static byte[] bytesArg(JSONArray args, int index) throws JSONException {
        String value = stringArg(args, index);
        if (value.isEmpty()) {
            return null;
        }
        String hex = value.indexOf(':') >= 0 ? value.replace(":", "") : value;
        if ((hex.length() & 1) != 0) {
            throw new IllegalArgumentException("Odd-length hex string: " + value);
        }
        byte[] data = new byte[hex.length() / 2];
        for (int i = 0; i < data.length; i++) {
            int offset = i * 2;
            data[i] = (byte) Integer.parseInt(hex.substring(offset, offset + 2), 16);
        }
        return data;
    }

    public boolean registerCallback(EventListener listener) {
        IP2p service = getService();
        if (service == null || listener == null) {
            return false;
        }
        eventListener = listener;
        try {
            callback = new IP2pCallback.Stub() {
                @Override
                public void onEvents(int what, String data) throws RemoteException {
                    dispatchP2pEvent(what, data);
                }
            };
            return service.registerCallback(callback.asBinder());
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean unregisterCallback() {
        IP2p service = getService();
        if (service == null || callback == null) {
            return false;
        }
        boolean ret = false;
        try {
            ret = service.unregisterCallback(callback.asBinder());
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        if (ret) {
            eventListener = null;
            callback = null;
        }
        return ret;
    }

    public String getDeviceAddress() {
        IP2p service = getService();
        if (service == null) {
            return null;
        }
        try {
            return service.p2p_get_device_address();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return null;
    }

    public String getNetworkBssid() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return "";
        }
        try {
            return service.getBssid();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public String getNetworkClientList() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return "";
        }
        try {
            return service.getClientList();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public int getNetworkId() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return -1;
        }
        try {
            return service.getId();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return -1;
    }

    public String getNetworkInterfaceName() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return "";
        }
        try {
            return service.getInterfaceName();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public String getNetworkSsid() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return "";
        }
        try {
            return service.getSsid();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return "";
    }

    public int getNetworkType() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return 0;
        }
        try {
            return service.getType();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return 0;
    }

    public boolean isNetworkCurrent() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return false;
        }
        try {
            return service.isCurrent();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean isNetworkGroupOwner() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return false;
        }
        try {
            return service.isGroupOwner();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean isNetworkPersistent() {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return false;
        }
        try {
            return service.isPersistent();
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }

    public boolean setNetworkClientList(String clients) {
        ISupplicantP2pNetwork service = getNetworkService();
        if (service == null) {
            return false;
        }
        try {
            service.setClientList(clients);
            return true;
        } catch (RemoteException e) {
            Log.e(TAG, e.getLocalizedMessage(), e);
        }
        return false;
    }
}
