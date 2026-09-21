# Client proxy for android.openfde.IP2pCallback
#
# This is a oneway AIDL callback interface implemented by the Android side
# and invoked by the supplicant owner. Here the Python side plays the HAL
# role, so this module marshals each callback into a binder transaction
# and sends it to the remote callback object.
#
# Transaction codes are assigned by AIDL in declaration order (1-based).
#
# Marshalling notes (libbinder conventions):
#   - byte, char, boolean and enums are transported as int32
#   - byte[] is written as int32 length followed by padded payload
#   - the *WithParams methods carry their parcelable fields flattened,
#     matching aidl/android/openfde/IP2pCallback.aidl

import gbinder
import logging
from enum import IntEnum, IntFlag


INTERFACE = "android.openfde.IP2pCallback"

TRANSACTION_onDeviceFound = 1
TRANSACTION_onDeviceLost = 2
TRANSACTION_onFindStopped = 3
TRANSACTION_onGoNegotiationCompleted = 4
TRANSACTION_onGoNegotiationRequest = 5
TRANSACTION_onGroupFormationFailure = 6
TRANSACTION_onGroupFormationSuccess = 7
TRANSACTION_onGroupRemoved = 8
TRANSACTION_onGroupStarted = 9
TRANSACTION_onInvitationReceived = 10
TRANSACTION_onInvitationResult = 11
TRANSACTION_onProvisionDiscoveryCompleted = 12
TRANSACTION_onR2DeviceFound = 13
TRANSACTION_onServiceDiscoveryResponse = 14
TRANSACTION_onStaAuthorized = 15
TRANSACTION_onStaDeauthorized = 16
TRANSACTION_onGroupFrequencyChanged = 17
TRANSACTION_onDeviceFoundWithVendorElements = 18
TRANSACTION_onGroupStartedWithParams = 19
TRANSACTION_onPeerClientJoined = 20
TRANSACTION_onPeerClientDisconnected = 21
TRANSACTION_onProvisionDiscoveryCompletedEvent = 22
TRANSACTION_onDeviceFoundWithParams = 23
TRANSACTION_onGoNegotiationRequestWithParams = 24
TRANSACTION_onInvitationReceivedWithParams = 25
TRANSACTION_onUsdBasedServiceDiscoveryResult = 26
TRANSACTION_onUsdBasedServiceDiscoveryTerminated = 27
TRANSACTION_onUsdBasedServiceAdvertisementTerminated = 28


class P2pStatusCode(IntEnum):
    SUCCESS = 0
    INFO_IS_CURRENTLY_UNAVAILABLE = 1
    INCOMPATIBLE_PARAMS = 2
    LIMIT_REACHED = 3
    INVALID_PARAMETER = 4
    UNABLE_TO_ACCOMMODATE_REQUEST = 5
    PREV_PROTOCOL_ERROR = 6
    NO_COMMON_CHANNEL = 7
    UNKNOWN_P2P_GROUP = 8
    BOTH_GO_INTENT_15 = 9
    INCOMPATIBLE_PROVISIONING_METHOD = 10
    REJECTED_BY_USER = 11
    UNKNOWN_ERROR = 12


class WpsDevPasswordId(IntEnum):
    DEFAULT = 0
    USER_SPECIFIED = 1
    MACHINE_SPECIFIED = 2
    REKEY = 3
    PUSH_BUTTON = 4
    REGISTRAR_SPECIFIED = 5
    NFC_CONNECTION_HANDOVER = 7


class WpsConfigMethods(IntFlag):
    USBA = 0x0001
    ETHERNET = 0x0002
    LABEL = 0x0004
    DISPLAY = 0x0008
    EXT_NFC_TOKEN = 0x0010
    INT_NFC_TOKEN = 0x0020
    NFC_INTERFACE = 0x0040
    PUSH_BUTTON = 0x0080
    KEYPAD = 0x0100
    VIRT_PUSH_BUTTON = 0x0280
    PHY_PUSH_BUTTON = 0x0480
    P2PS = 0x1000
    VIRT_DISPLAY = 0x2008
    PHY_DISPLAY = 0x4008


class P2pProvDiscStatusCode(IntEnum):
    SUCCESS = 0
    TIMEOUT = 1
    REJECTED = 2
    INFO_UNAVAILABLE = 3


class P2pGroupCapabilityMask(IntFlag):
    GROUP_OWNER = 0x01
    PERSISTENT_GROUP = 0x02
    GROUP_LIMIT = 0x04
    INTRA_BSS_DIST = 0x08
    CROSS_CONNECTION = 0x10
    PERSISTENT_RECONNECT = 0x20
    GROUP_FORMATION = 0x40
    IP_ADDR_ALLOCATION = 0x80


def _to_bytes(value):
    if value is None:
        return None
    if isinstance(value, str):
        return bytes(int(part, 16) for part in value.split(':'))
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    return bytes(value)


def _append_byte_array(request, value):
    data = _to_bytes(value)
    if data is None:
        request.append_int32(-1)
        return
    for method_name in ("append_byte_array", "append_bytes", "append_buffer"):
        method = getattr(request, method_name, None)
        if method is not None:
            method(data)
            return
    raise NotImplementedError("gbinder writer has no byte array method")


def _append_field(request, value):
    if value is None or isinstance(value, (bytes, bytearray, memoryview)):
        _append_byte_array(request, value)
    elif isinstance(value, str) and ':' in value:
        _append_byte_array(request, value)
    elif isinstance(value, str):
        request.append_string16(value)
    else:
        request.append_int32(int(value))


class ISupplicantP2pIfaceCallback:
    def __init__(self, remote, interface=INTERFACE):
        self.client = gbinder.Client(remote, interface)

    def _send(self, code, request):
        try:
            status = self.client.transact_sync_oneway(code, request)
        except Exception as e:
            logging.error("{} transaction {} failed: {}".format(INTERFACE, code, e))
            return False
        if status:
            logging.error("{} transaction {} returned status {}".format(INTERFACE, code, status))
            return False
        return True

    def onDeviceFound(self, srcAddress, p2pDeviceAddress, primaryDeviceType, deviceName,
                      configMethods, deviceCapabilities, groupCapabilities, wfdDeviceInfo):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        _append_byte_array(request, primaryDeviceType)
        request.append_string16(deviceName if deviceName is not None else "")
        request.append_int32(int(configMethods))
        request.append_int32(int(deviceCapabilities))
        request.append_int32(int(groupCapabilities))
        _append_byte_array(request, wfdDeviceInfo)
        return self._send(TRANSACTION_onDeviceFound, request)

    def onDeviceLost(self, p2pDeviceAddress):
        request = self.client.new_request()
        _append_byte_array(request, p2pDeviceAddress)
        return self._send(TRANSACTION_onDeviceLost, request)

    def onFindStopped(self):
        request = self.client.new_request()
        return self._send(TRANSACTION_onFindStopped, request)

    def onGoNegotiationCompleted(self, status):
        request = self.client.new_request()
        request.append_int32(int(status))
        return self._send(TRANSACTION_onGoNegotiationCompleted, request)

    def onGoNegotiationRequest(self, srcAddress, passwordId):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        request.append_int32(int(passwordId))
        return self._send(TRANSACTION_onGoNegotiationRequest, request)

    def onGroupFormationFailure(self, failureReason):
        request = self.client.new_request()
        request.append_string16(failureReason if failureReason is not None else "")
        return self._send(TRANSACTION_onGroupFormationFailure, request)

    def onGroupFormationSuccess(self):
        request = self.client.new_request()
        return self._send(TRANSACTION_onGroupFormationSuccess, request)

    def onGroupRemoved(self, groupIfname, isGroupOwner):
        request = self.client.new_request()
        request.append_string16(groupIfname if groupIfname is not None else "")
        request.append_int32(1 if isGroupOwner else 0)
        return self._send(TRANSACTION_onGroupRemoved, request)

    def onGroupStarted(self, groupIfname, isGroupOwner, ssid, frequency, psk,
                       passphrase, goDeviceAddress, isPersistent):
        request = self.client.new_request()
        request.append_string16(groupIfname if groupIfname is not None else "")
        request.append_int32(1 if isGroupOwner else 0)
        _append_byte_array(request, ssid)
        request.append_int32(int(frequency))
        _append_byte_array(request, psk)
        request.append_string16(passphrase if passphrase is not None else "")
        _append_byte_array(request, goDeviceAddress)
        request.append_int32(1 if isPersistent else 0)
        return self._send(TRANSACTION_onGroupStarted, request)

    def onInvitationReceived(self, srcAddress, goDeviceAddress, bssid,
                             persistentNetworkId, operatingFrequency):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, goDeviceAddress)
        _append_byte_array(request, bssid)
        request.append_int32(int(persistentNetworkId))
        request.append_int32(int(operatingFrequency))
        return self._send(TRANSACTION_onInvitationReceived, request)

    def onInvitationResult(self, bssid, status):
        request = self.client.new_request()
        _append_byte_array(request, bssid)
        request.append_int32(int(status))
        return self._send(TRANSACTION_onInvitationResult, request)

    def onProvisionDiscoveryCompleted(self, p2pDeviceAddress, isRequest, status,
                                      configMethods, generatedPin):
        request = self.client.new_request()
        _append_byte_array(request, p2pDeviceAddress)
        request.append_int32(1 if isRequest else 0)
        request.append_int32(int(status))
        request.append_int32(int(configMethods))
        request.append_string16(generatedPin if generatedPin is not None else "")
        return self._send(TRANSACTION_onProvisionDiscoveryCompleted, request)

    def onR2DeviceFound(self, srcAddress, p2pDeviceAddress, primaryDeviceType, deviceName,
                        configMethods, deviceCapabilities, groupCapabilities,
                        wfdDeviceInfo, wfdR2DeviceInfo):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        _append_byte_array(request, primaryDeviceType)
        request.append_string16(deviceName if deviceName is not None else "")
        request.append_int32(int(configMethods))
        request.append_int32(int(deviceCapabilities))
        request.append_int32(int(groupCapabilities))
        _append_byte_array(request, wfdDeviceInfo)
        _append_byte_array(request, wfdR2DeviceInfo)
        return self._send(TRANSACTION_onR2DeviceFound, request)

    def onServiceDiscoveryResponse(self, srcAddress, updateIndicator, tlvs):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        request.append_int32(int(updateIndicator))
        _append_byte_array(request, tlvs)
        return self._send(TRANSACTION_onServiceDiscoveryResponse, request)

    def onStaAuthorized(self, srcAddress, p2pDeviceAddress):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        return self._send(TRANSACTION_onStaAuthorized, request)

    def onStaDeauthorized(self, srcAddress, p2pDeviceAddress):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        return self._send(TRANSACTION_onStaDeauthorized, request)

    def onGroupFrequencyChanged(self, groupIfname, frequency):
        request = self.client.new_request()
        request.append_string16(groupIfname if groupIfname is not None else "")
        request.append_int32(int(frequency))
        return self._send(TRANSACTION_onGroupFrequencyChanged, request)

    def onDeviceFoundWithVendorElements(self, srcAddress, p2pDeviceAddress,
                                        primaryDeviceType, deviceName, configMethods,
                                        deviceCapabilities, groupCapabilities,
                                        wfdDeviceInfo, wfdR2DeviceInfo, vendorElemBytes):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        _append_byte_array(request, primaryDeviceType)
        request.append_string16(deviceName if deviceName is not None else "")
        request.append_int32(int(configMethods))
        request.append_int32(int(deviceCapabilities))
        request.append_int32(int(groupCapabilities))
        _append_byte_array(request, wfdDeviceInfo)
        _append_byte_array(request, wfdR2DeviceInfo)
        _append_byte_array(request, vendorElemBytes)
        return self._send(TRANSACTION_onDeviceFoundWithVendorElements, request)

    # *WithParams callbacks carry their parcelable fields flattened, in the
    # same order as declared in aidl/android/openfde/IP2pCallback.aidl.

    def onGroupStartedWithParams(self, groupInterfaceName, isGroupOwner, ssid,
                                 frequencyMHz, psk, passphrase, goDeviceAddress,
                                 isPersistent):
        request = self.client.new_request()
        request.append_string16(groupInterfaceName if groupInterfaceName is not None else "")
        request.append_int32(1 if isGroupOwner else 0)
        _append_byte_array(request, ssid)
        request.append_int32(int(frequencyMHz))
        _append_byte_array(request, psk)
        request.append_string16(passphrase if passphrase is not None else "")
        _append_byte_array(request, goDeviceAddress)
        request.append_int32(1 if isPersistent else 0)
        return self._send(TRANSACTION_onGroupStartedWithParams, request)

    def onPeerClientJoined(self, srcAddress, p2pDeviceAddress, isVpSupported):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        request.append_int32(1 if isVpSupported else 0)
        return self._send(TRANSACTION_onPeerClientJoined, request)

    def onPeerClientDisconnected(self, srcAddress, p2pDeviceAddress):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        return self._send(TRANSACTION_onPeerClientDisconnected, request)

    def onProvisionDiscoveryCompletedEvent(self, p2pDeviceAddress, status,
                                           configMethods, generatedPin):
        request = self.client.new_request()
        _append_byte_array(request, p2pDeviceAddress)
        request.append_int32(int(status))
        request.append_int32(int(configMethods))
        request.append_string16(generatedPin if generatedPin is not None else "")
        return self._send(TRANSACTION_onProvisionDiscoveryCompletedEvent, request)

    def onDeviceFoundWithParams(self, srcAddress, p2pDeviceAddress, primaryDeviceType,
                                deviceName, configMethods, deviceCapabilities,
                                groupCapabilities, wfdDeviceInfo, wfdR2DeviceInfo,
                                vendorElem):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, p2pDeviceAddress)
        _append_byte_array(request, primaryDeviceType)
        request.append_string16(deviceName if deviceName is not None else "")
        request.append_int32(int(configMethods))
        request.append_int32(int(deviceCapabilities))
        request.append_int32(int(groupCapabilities))
        _append_byte_array(request, wfdDeviceInfo)
        _append_byte_array(request, wfdR2DeviceInfo)
        _append_byte_array(request, vendorElem)
        return self._send(TRANSACTION_onDeviceFoundWithParams, request)

    def onGoNegotiationRequestWithParams(self, srcAddress, passwordId, goIntent):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        request.append_int32(int(passwordId))
        request.append_int32(int(goIntent))
        return self._send(TRANSACTION_onGoNegotiationRequestWithParams, request)

    def onInvitationReceivedWithParams(self, srcAddress, goDeviceAddress, bssid,
                                       persistentNetworkId, operatingFrequencyMHz):
        request = self.client.new_request()
        _append_byte_array(request, srcAddress)
        _append_byte_array(request, goDeviceAddress)
        _append_byte_array(request, bssid)
        request.append_int32(int(persistentNetworkId))
        request.append_int32(int(operatingFrequencyMHz))
        return self._send(TRANSACTION_onInvitationReceivedWithParams, request)

    def onUsdBasedServiceDiscoveryResult(self, sessionId, srcAddress,
                                         updateIndicator, tlvs):
        request = self.client.new_request()
        request.append_int32(int(sessionId))
        _append_byte_array(request, srcAddress)
        request.append_int32(int(updateIndicator))
        _append_byte_array(request, tlvs)
        return self._send(TRANSACTION_onUsdBasedServiceDiscoveryResult, request)

    def onUsdBasedServiceDiscoveryTerminated(self, sessionId, reasonCode):
        request = self.client.new_request()
        request.append_int32(int(sessionId))
        request.append_int32(int(reasonCode))
        return self._send(TRANSACTION_onUsdBasedServiceDiscoveryTerminated, request)

    def onUsdBasedServiceAdvertisementTerminated(self, sessionId, reasonCode):
        request = self.client.new_request()
        request.append_int32(int(sessionId))
        request.append_int32(int(reasonCode))
        return self._send(TRANSACTION_onUsdBasedServiceAdvertisementTerminated, request)
