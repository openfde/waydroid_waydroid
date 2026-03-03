import gbinder
import logging
import threading
from tools import helpers
from enum import Enum

from gi.repository import GLib


INTERFACE = "android.openfde.IBluetooth"
SERVICE_NAME = "openfdebluetooth"

def addService(args, registerCallback, unregisterCallback, init, cleanup, enable,
                  disable, getAdapterProperties, getAdapterProperty, setAdapterProperty,
                  createBond, removeBond, cancelBond, pairingIsBusy, getConnectionState,
                  startDiscovery, cancelDiscovery, connect, disconnect, setDeviceProperty,
                  startMonitoring):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    class Transaction(Enum):
        REGISTER_CALLBACK = 1
        UNREGISTER_CALLBACK = 2
        INIT = 3
        CLEANUP = 4
        ENABLE = 5
        DISABLE = 6
        GET_ADAPTER_PROPERTIES = 7
        GET_ADAPTER_PROPERTY = 8
        SET_ADAPTER_PROPERTY = 9
        CREATE_BOND = 10
        REMOVE_BOND = 11
        CANCEL_BOND = 12
        PAIRING_IS_BUSY = 13
        GET_CONNECTION_STATE = 14
        START_DISCOVERY = 15
        CANCEL_DISCOVERY = 16
        CONNECT = 17
        DISCONNECT = 18
        SET_DEVICE_PROPERTY = 19

    def responseHandlerThread(req, code, flags, localResponse):
        reader = req.init_reader()
        if code == Transaction.UNREGISTER_CALLBACK.value:
            callback = reader.read_object()
            ret = unregisterCallback(callback)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.CREATE_BOND.value:
            address = reader.read_string16()
            status, addressType = reader.read_int32()
            status, transport = reader.read_int32()
            ret = createBond(address, addressType, transport)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.GET_CONNECTION_STATE.value:
            address = reader.read_string16()
            ret = getConnectionState(address)
            localResponse.append_int32(0)
            localResponse.append_int32(ret)
        elif code == Transaction.GET_ADAPTER_PROPERTIES.value:
            ret = getAdapterProperties()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.GET_ADAPTER_PROPERTY.value:
            status, type = reader.read_int32()
            ret = getAdapterProperty(type)
            localResponse.append_int32(0)
            localResponse.append_bool(True)
        elif code == Transaction.START_DISCOVERY.value:
            ret = startDiscovery()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        req.complete(localResponse, 0)
    
    def responseHandler(req, code, flags):
        logging.verbose(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        asyncTransaction = [
            Transaction.UNREGISTER_CALLBACK.value,
            Transaction.CREATE_BOND.value,
            Transaction.GET_CONNECTION_STATE.value,
            Transaction.GET_ADAPTER_PROPERTIES.value,
            Transaction.GET_ADAPTER_PROPERTY.value,
            Transaction.START_DISCOVERY.value
        ]
        startMonitoring()
        if code in asyncTransaction:
            localResponse = response.new_reply()
            req.block()
            threading.Thread(target=responseHandlerThread, args=(req, code, flags, localResponse)).start()
            return localResponse, 0
        reader = req.init_reader()
        localResponse = response.new_reply()
        if code == Transaction.REGISTER_CALLBACK.value:
            callback = reader.read_object()
            ret = registerCallback(callback)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.INIT.value:
            ret = init()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.CLEANUP.value:
            ret = cleanup()
            localResponse.append_int32(0)
        elif code == Transaction.ENABLE.value:
            ret = enable()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.DISABLE.value:
            ret = disable()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.SET_ADAPTER_PROPERTY.value:
            status, type = reader.read_int32()
            val = reader.read_string16()
            ret = setAdapterProperty(type, val)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.REMOVE_BOND.value:
            address = reader.read_string16()
            ret = removeBond(address)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.CANCEL_BOND.value:
            address = reader.read_string16()
            ret = cancelBond(address)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.PAIRING_IS_BUSY.value:
            ret = pairingIsBusy()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.CANCEL_DISCOVERY.value:
            ret = cancelDiscovery()
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.CONNECT.value:
            address = reader.read_string16()
            ret = connect(address)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.DISCONNECT.value:
            address = reader.read_string16()
            ret = disconnect(address)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        elif code == Transaction.SET_DEVICE_PROPERTY.value:
            address = reader.read_string16()
            status, type = reader.read_int32()
            val = reader.read_string16()
            ret = setDeviceProperty(address, type, val)
            localResponse.append_int32(0)
            localResponse.append_bool(ret)
        else:
            logging.error("{} unknown code: {}".format(INTERFACE, code))
            localResponse.append_int32(0)
            localResponse.append_int32(0)
        return localResponse, 0

    def binderPresence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.bluetoothLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, responseHandler)
    args.bluetoothLoop = GLib.MainLoop()
    binderPresence()
    status = serviceManager.add_presence_handler(binderPresence)
    if status:
        args.bluetoothLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
