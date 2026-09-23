import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "android.openfde.ISupplicantP2pNetwork"
SERVICE_NAME = "openfdep2pnetwork"

TRANSACTION_getBssid = 1
TRANSACTION_getClientList = 2
TRANSACTION_getId = 3
TRANSACTION_getInterfaceName = 4
TRANSACTION_getSsid = 5
TRANSACTION_getType = 6
TRANSACTION_isCurrent = 7
TRANSACTION_isGroupOwner = 8
TRANSACTION_isPersistent = 9
TRANSACTION_setClientList = 10


def _read_string16(reader):
    try:
        return reader.read_string16()
    except Exception:
        return ""


def add_service(
    args,
    getBssid,
    getClientList,
    getId,
    getInterfaceName,
    getSsid,
    getType,
    isCurrent,
    isGroupOwner,
    isPersistent,
    setClientList,
):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    def response_handler(req, code, flags):
        logging.debug("{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        local_response = response.new_reply()

        if code == TRANSACTION_getBssid:
            ret = getBssid()
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_getClientList:
            ret = getClientList()
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_getId:
            local_response.append_int32(0)
            local_response.append_int32(int(getId()))
        elif code == TRANSACTION_getInterfaceName:
            ret = getInterfaceName()
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_getSsid:
            ret = getSsid()
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_getType:
            local_response.append_int32(0)
            local_response.append_int32(int(getType()))
        elif code == TRANSACTION_isCurrent:
            local_response.append_int32(0)
            local_response.append_bool(bool(isCurrent()))
        elif code == TRANSACTION_isGroupOwner:
            local_response.append_int32(0)
            local_response.append_bool(bool(isGroupOwner()))
        elif code == TRANSACTION_isPersistent:
            local_response.append_int32(0)
            local_response.append_bool(bool(isPersistent()))
        elif code == TRANSACTION_setClientList:
            setClientList(_read_string16(reader))
            local_response.append_int32(0)
        else:
            logging.error("{} unknown code: {}".format(INTERFACE, code))
            local_response.append_int32(0)
            local_response.append_int32(0)

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(SERVICE_NAME, status))
                args.p2pNetworkLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.p2pNetworkLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.p2pNetworkLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))