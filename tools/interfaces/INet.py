import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "lineageos.waydroid.INet"
SERVICE_NAME = "fdenet"

TRANSACTION_setStaticIp = 1
TRANSACTION_setDHCP = 2
TRANSACTION_getAllSsid = 3
TRANSACTION_connectSsid = 4
TRANSACTION_getActivedWifi = 5
TRANSACTION_connectActivedWifi = 6
TRANSACTION_enableWifi = 7
TRANSACTION_connectedWifiList = 8
TRANSACTION_isWifiEnable = 9
TRANSACTION_getSignalAndSecurity = 10
TRANSACTION_connectHidedWifi = 11
TRANSACTION_forgetWifi = 12
TRANSACTION_getStaticIpConf = 13
TRANSACTION_getActivedInterface = 14
TRANSACTION_getIpConfigure = 15
TRANSACTION_getDns = 16


def add_service(args, setStaticIp, setDHCP, getAllSsid, connectSsid, getActivedWifi, 
    connectActivedWifi, enableWifi, connectedWifiList, isWifiEnable, getSignalAndSecurity, 
    connectHidedWifi, forgetWifi, getStaticIpConf, getActivedInterface, getIpConfigure, getDns):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    def response_handler(req, code, flags):
        logging.debug(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        local_response = response.new_reply()
        if code == TRANSACTION_setStaticIp:
            arg1 = reader.read_string16()
            arg2 = reader.read_string16()
            status, arg3 = reader.read_int32()
            arg4 = reader.read_string16()
            arg5 = reader.read_string16()
            arg6 = reader.read_string16()
            ret = setStaticIp(arg1, arg2, arg3, arg4, arg5, arg6)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_setDHCP:
            arg1 = reader.read_string16()
            ret = setDHCP(arg1)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_getAllSsid:
            ret = getAllSsid()
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_connectSsid:
            arg1 = reader.read_string16()
            arg2 = reader.read_string16()
            ret = connectSsid(arg1, arg2)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_getActivedWifi:
            ret = getActivedWifi()
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_connectActivedWifi:
            arg1 = reader.read_string16()
            status, arg2 = reader.read_int32()
            ret = connectActivedWifi(arg1, arg2)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_enableWifi:
            status, arg1 = reader.read_int32()
            ret = enableWifi(arg1)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_connectedWifiList:
            ret = connectedWifiList()
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_isWifiEnable:
            ret = isWifiEnable()
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_getSignalAndSecurity:
            arg1 = reader.read_string16()
            ret = getSignalAndSecurity(arg1)
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_connectHidedWifi:
            arg1 = reader.read_string16()
            arg2 = reader.read_string16()
            ret = connectHidedWifi(arg1, arg2)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_forgetWifi:
            arg1 = reader.read_string16()
            ret = forgetWifi(arg1)
            local_response.append_int32(0)
            local_response.append_int32(ret)
        if code == TRANSACTION_getStaticIpConf:
            arg1 = reader.read_string16()
            ret = getStaticIpConf(arg1)
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_getActivedInterface:
            ret = getActivedInterface()
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_getIpConfigure:
            arg1 = reader.read_string16()
            ret = getIpConfigure(arg1)
            local_response.append_int32(0)
            local_response.append_string16(ret)
        if code == TRANSACTION_getDns:
            arg1 = reader.read_string16()
            ret = getDns(arg1)
            local_response.append_int32(0)
            local_response.append_string16(ret)
        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.netLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.netLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.netLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
