# Client proxy for android.openfde.IP2pCallback
#
# This is a oneway AIDL callback interface implemented by the Android side
# and invoked by the supplicant owner. Here the Python side plays the HAL
# role, so this module marshals each callback into a binder transaction
# and sends it to the remote callback object.
#
# Transaction codes are assigned by AIDL in declaration order (1-based).

import gbinder
import logging
from enum import IntEnum, IntFlag


INTERFACE = "android.openfde.IP2pCallback"

TRANSACTION_onEvents = 1


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

    def onEvents(self, what, data):
        request = self.client.new_request()
        request.append_int32(int(what))
        request.append_string16(data)
        return self._send(TRANSACTION_onEvents, request)
