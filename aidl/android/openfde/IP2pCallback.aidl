package android.openfde;

// Mirror of android.hardware.wifi.supplicant.ISupplicantP2pIfaceCallback.
// Enum types from the AOSP interface are transported as int, byte/char are
// widened to int, and the *WithParams parcelables are flattened into plain
// parameters. Method order matches the AOSP declaration order exactly, so
// the auto-generated transaction codes (1-based) are identical.
oneway interface IP2pCallback {
    void onDeviceFound(in byte[] srcAddress, in byte[] p2pDeviceAddress,
            in byte[] primaryDeviceType, in String deviceName, int configMethods,
            int deviceCapabilities, int groupCapabilities, in byte[] wfdDeviceInfo);

    void onDeviceLost(in byte[] p2pDeviceAddress);

    void onFindStopped();

    void onGoNegotiationCompleted(int status);

    void onGoNegotiationRequest(in byte[] srcAddress, int passwordId);

    void onGroupFormationFailure(in String failureReason);

    void onGroupFormationSuccess();

    void onGroupRemoved(in String groupIfname, boolean isGroupOwner);

    void onGroupStarted(in String groupIfname, boolean isGroupOwner, in byte[] ssid,
            int frequency, in byte[] psk, in String passphrase, in byte[] goDeviceAddress,
            boolean isPersistent);

    void onInvitationReceived(in byte[] srcAddress, in byte[] goDeviceAddress, in byte[] bssid,
            int persistentNetworkId, int operatingFrequency);

    void onInvitationResult(in byte[] bssid, int status);

    void onProvisionDiscoveryCompleted(in byte[] p2pDeviceAddress, boolean isRequest,
            int status, int configMethods, in String generatedPin);

    void onR2DeviceFound(in byte[] srcAddress, in byte[] p2pDeviceAddress,
            in byte[] primaryDeviceType, in String deviceName, int configMethods,
            int deviceCapabilities, int groupCapabilities,
            in byte[] wfdDeviceInfo, in byte[] wfdR2DeviceInfo);

    void onServiceDiscoveryResponse(in byte[] srcAddress, int updateIndicator, in byte[] tlvs);

    void onStaAuthorized(in byte[] srcAddress, in byte[] p2pDeviceAddress);

    void onStaDeauthorized(in byte[] srcAddress, in byte[] p2pDeviceAddress);

    void onGroupFrequencyChanged(in String groupIfname, int frequency);

    void onDeviceFoundWithVendorElements(in byte[] srcAddress, in byte[] p2pDeviceAddress,
            in byte[] primaryDeviceType, in String deviceName, int configMethods,
            int deviceCapabilities, int groupCapabilities,
            in byte[] wfdDeviceInfo, in byte[] wfdR2DeviceInfo, in byte[] vendorElemBytes);

    void onGroupStartedWithParams(in String groupInterfaceName, boolean isGroupOwner,
            in byte[] ssid, int frequencyMHz, in byte[] psk, in String passphrase,
            in byte[] goDeviceAddress, boolean isPersistent);

    void onPeerClientJoined(in byte[] srcAddress, in byte[] p2pDeviceAddress,
            boolean isVpSupported);

    void onPeerClientDisconnected(in byte[] srcAddress, in byte[] p2pDeviceAddress);

    void onProvisionDiscoveryCompletedEvent(in byte[] p2pDeviceAddress, int status,
            int configMethods, in String generatedPin);

    void onDeviceFoundWithParams(in byte[] srcAddress, in byte[] p2pDeviceAddress,
            in byte[] primaryDeviceType, in String deviceName, int configMethods,
            int deviceCapabilities, int groupCapabilities, in byte[] wfdDeviceInfo,
            in byte[] wfdR2DeviceInfo, in byte[] vendorElem);

    void onGoNegotiationRequestWithParams(in byte[] srcAddress, int passwordId, int goIntent);

    void onInvitationReceivedWithParams(in byte[] srcAddress, in byte[] goDeviceAddress,
            in byte[] bssid, int persistentNetworkId, int operatingFrequencyMHz);

    void onUsdBasedServiceDiscoveryResult(int sessionId, in byte[] srcAddress,
            int updateIndicator, in byte[] tlvs);

    void onUsdBasedServiceDiscoveryTerminated(int sessionId, int reasonCode);

    void onUsdBasedServiceAdvertisementTerminated(int sessionId, int reasonCode);
}
