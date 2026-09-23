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



public class P2p {
    private static final String TAG = "fdep2p";
    public static final String SERVICE_NAME = "android.openfde.IP2p";

    private static IP2p sService;
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

    public boolean registerCallback(EventListener listener) {
        IP2p service = getService();
        if (service == null || listener == null) {
            return false;
        }
        eventListener = listener;
        try {
            callback = new IP2pCallback.Stub() {
                @Override
                public void onDeviceFound(byte[] srcAddress, byte[] p2pDeviceAddress,
                        byte[] primaryDeviceType, String deviceName, int configMethods,
                        int deviceCapabilities, int groupCapabilities,
                        byte[] wfdDeviceInfo) throws RemoteException {
                    eventListener.onDeviceFound(srcAddress, p2pDeviceAddress, primaryDeviceType,
                            deviceName, configMethods, deviceCapabilities, groupCapabilities,
                            wfdDeviceInfo);
                }

                @Override
                public void onDeviceLost(byte[] p2pDeviceAddress) throws RemoteException {
                    eventListener.onDeviceLost(p2pDeviceAddress);
                }

                @Override
                public void onFindStopped() throws RemoteException {
                    eventListener.onFindStopped();
                }

                @Override
                public void onGoNegotiationCompleted(int status) throws RemoteException {
                    eventListener.onGoNegotiationCompleted(status);
                }

                @Override
                public void onGoNegotiationRequest(byte[] srcAddress,
                        int passwordId) throws RemoteException {
                    eventListener.onGoNegotiationRequest(srcAddress, passwordId);
                }

                @Override
                public void onGroupFormationFailure(String failureReason) throws RemoteException {
                    eventListener.onGroupFormationFailure(failureReason);
                }

                @Override
                public void onGroupFormationSuccess() throws RemoteException {
                    eventListener.onGroupFormationSuccess();
                }

                @Override
                public void onGroupRemoved(String groupIfname,
                        boolean isGroupOwner) throws RemoteException {
                    eventListener.onGroupRemoved(groupIfname, isGroupOwner);
                }

                @Override
                public void onGroupStarted(String groupIfname, boolean isGroupOwner, byte[] ssid,
                        int frequency, byte[] psk, String passphrase, byte[] goDeviceAddress,
                        boolean isPersistent) throws RemoteException {
                    eventListener.onGroupStarted(groupIfname, isGroupOwner, ssid, frequency, psk,
                            passphrase, goDeviceAddress, isPersistent);
                }

                @Override
                public void onInvitationReceived(byte[] srcAddress, byte[] goDeviceAddress,
                        byte[] bssid, int persistentNetworkId,
                        int operatingFrequency) throws RemoteException {
                    eventListener.onInvitationReceived(srcAddress, goDeviceAddress, bssid,
                            persistentNetworkId, operatingFrequency);
                }

                @Override
                public void onInvitationResult(byte[] bssid, int status) throws RemoteException {
                    eventListener.onInvitationResult(bssid, status);
                }

                @Override
                public void onProvisionDiscoveryCompleted(byte[] p2pDeviceAddress,
                        boolean isRequest, int status, int configMethods,
                        String generatedPin) throws RemoteException {
                    eventListener.onProvisionDiscoveryCompleted(p2pDeviceAddress, isRequest,
                            status, configMethods, generatedPin);
                }

                @Override
                public void onR2DeviceFound(byte[] srcAddress, byte[] p2pDeviceAddress,
                        byte[] primaryDeviceType, String deviceName, int configMethods,
                        int deviceCapabilities, int groupCapabilities, byte[] wfdDeviceInfo,
                        byte[] wfdR2DeviceInfo) throws RemoteException {
                    eventListener.onR2DeviceFound(srcAddress, p2pDeviceAddress, primaryDeviceType,
                            deviceName, configMethods, deviceCapabilities, groupCapabilities,
                            wfdDeviceInfo, wfdR2DeviceInfo);
                }

                @Override
                public void onServiceDiscoveryResponse(byte[] srcAddress, int updateIndicator,
                        byte[] tlvs) throws RemoteException {
                    eventListener.onServiceDiscoveryResponse(srcAddress, updateIndicator, tlvs);
                }

                @Override
                public void onStaAuthorized(byte[] srcAddress,
                        byte[] p2pDeviceAddress) throws RemoteException {
                    eventListener.onStaAuthorized(srcAddress, p2pDeviceAddress);
                }

                @Override
                public void onStaDeauthorized(byte[] srcAddress,
                        byte[] p2pDeviceAddress) throws RemoteException {
                    eventListener.onStaDeauthorized(srcAddress, p2pDeviceAddress);
                }

                @Override
                public void onGroupFrequencyChanged(String groupIfname,
                        int frequency) throws RemoteException {
                    eventListener.onGroupFrequencyChanged(groupIfname, frequency);
                }

                @Override
                public void onDeviceFoundWithVendorElements(byte[] srcAddress,
                        byte[] p2pDeviceAddress, byte[] primaryDeviceType, String deviceName,
                        int configMethods, int deviceCapabilities, int groupCapabilities,
                        byte[] wfdDeviceInfo, byte[] wfdR2DeviceInfo,
                        byte[] vendorElemBytes) throws RemoteException {
                    eventListener.onDeviceFoundWithVendorElements(srcAddress, p2pDeviceAddress,
                            primaryDeviceType, deviceName, configMethods, deviceCapabilities,
                            groupCapabilities, wfdDeviceInfo, wfdR2DeviceInfo, vendorElemBytes);
                }

                @Override
                public void onGroupStartedWithParams(String groupInterfaceName,
                        boolean isGroupOwner, byte[] ssid, int frequencyMHz, byte[] psk,
                        String passphrase, byte[] goDeviceAddress,
                        boolean isPersistent) throws RemoteException {
                    eventListener.onGroupStartedWithParams(groupInterfaceName, isGroupOwner, ssid,
                            frequencyMHz, psk, passphrase, goDeviceAddress, isPersistent);
                }

                @Override
                public void onPeerClientJoined(byte[] srcAddress, byte[] p2pDeviceAddress,
                        boolean isVpSupported) throws RemoteException {
                    eventListener.onPeerClientJoined(srcAddress, p2pDeviceAddress, isVpSupported);
                }

                @Override
                public void onPeerClientDisconnected(byte[] srcAddress,
                        byte[] p2pDeviceAddress) throws RemoteException {
                    eventListener.onPeerClientDisconnected(srcAddress, p2pDeviceAddress);
                }

                @Override
                public void onProvisionDiscoveryCompletedEvent(byte[] p2pDeviceAddress, int status,
                        int configMethods, String generatedPin) throws RemoteException {
                    eventListener.onProvisionDiscoveryCompletedEvent(p2pDeviceAddress, status,
                            configMethods, generatedPin);
                }

                @Override
                public void onDeviceFoundWithParams(byte[] srcAddress, byte[] p2pDeviceAddress,
                        byte[] primaryDeviceType, String deviceName, int configMethods,
                        int deviceCapabilities, int groupCapabilities, byte[] wfdDeviceInfo,
                        byte[] wfdR2DeviceInfo, byte[] vendorElem) throws RemoteException {
                    eventListener.onDeviceFoundWithParams(srcAddress, p2pDeviceAddress,
                            primaryDeviceType, deviceName, configMethods, deviceCapabilities,
                            groupCapabilities, wfdDeviceInfo, wfdR2DeviceInfo, vendorElem);
                }

                @Override
                public void onGoNegotiationRequestWithParams(byte[] srcAddress, int passwordId,
                        int goIntent) throws RemoteException {
                    eventListener.onGoNegotiationRequestWithParams(srcAddress, passwordId,
                            goIntent);
                }

                @Override
                public void onInvitationReceivedWithParams(byte[] srcAddress,
                        byte[] goDeviceAddress, byte[] bssid, int persistentNetworkId,
                        int operatingFrequencyMHz) throws RemoteException {
                    eventListener.onInvitationReceivedWithParams(srcAddress, goDeviceAddress,
                            bssid, persistentNetworkId, operatingFrequencyMHz);
                }

                @Override
                public void onUsdBasedServiceDiscoveryResult(int sessionId, byte[] srcAddress,
                        int updateIndicator, byte[] tlvs) throws RemoteException {
                    eventListener.onUsdBasedServiceDiscoveryResult(sessionId, srcAddress,
                            updateIndicator, tlvs);
                }

                @Override
                public void onUsdBasedServiceDiscoveryTerminated(int sessionId,
                        int reasonCode) throws RemoteException {
                    eventListener.onUsdBasedServiceDiscoveryTerminated(sessionId, reasonCode);
                }

                @Override
                public void onUsdBasedServiceAdvertisementTerminated(int sessionId,
                        int reasonCode) throws RemoteException {
                    eventListener.onUsdBasedServiceAdvertisementTerminated(sessionId, reasonCode);
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
}
