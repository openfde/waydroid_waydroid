# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import gbinder
import logging
from enum import Enum

from tools import helpers
from gi.repository import GLib


INTERFACE = "android.openfde.IWifi"
SERVICE_NAME = "openfdewifi"


def addService(args, registerCallback, unregisterCallback, init, isEnabled, setEnabled,
               startScan, getConnectionInfo, getScanResults, connect, connectSaved, disconnect,
               getSavedNetworks, saveNetwork, forgetNetwork, getFactoryMacAddresses, getDhcpInfo):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager(
            "/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    class Transaction(Enum):
        REGISTER_CALLBACK = 1
        UNREGISTER_CALLBACK = 2
        INIT = 3
        IS_ENABLED = 4
        SET_ENABLED = 5
        START_SCAN = 6
        GET_CONNECTION_INFO = 7
        GET_SCAN_RESULTS = 8
        CONNECT = 9
        CONNECT_SAVED = 10
        DISCONNECT = 11
        GET_SAVED_NETWORKS = 12
        SAVE_NETWORK = 13
        FORGET_NETWORK = 14
        GET_FACTORY_MAC_ADDRESSES = 15
        GET_DHCP_INFO = 16

    def responseHandler(req, code, flags):
        logging.verbose("{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        localResponse = response.new_reply()
        try:
            if code == Transaction.REGISTER_CALLBACK.value:
                callback = reader.read_object()
                ret = registerCallback(callback)
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.UNREGISTER_CALLBACK.value:
                callback = reader.read_object()
                ret = unregisterCallback(callback)
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.INIT.value:
                ret = init()
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.IS_ENABLED.value:
                ret = isEnabled()
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.SET_ENABLED.value:
                status, on = reader.read_bool()
                ret = setEnabled(bool(on))
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.START_SCAN.value:
                ret = startScan()
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.GET_CONNECTION_INFO.value:
                ret = getConnectionInfo()
                localResponse.append_int32(0)
                localResponse.append_string16(ret or "{}")
            elif code == Transaction.GET_SCAN_RESULTS.value:
                ret = getScanResults()
                localResponse.append_int32(0)
                localResponse.append_string16(ret or "{}")
            elif code == Transaction.CONNECT.value:
                ssid = reader.read_string16()
                status, security = reader.read_int32()
                passphrase = reader.read_string16()
                ret = connect(ssid, security, passphrase)
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.CONNECT_SAVED.value:
                name = reader.read_string16()
                ret = connectSaved(name)
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.DISCONNECT.value:
                ret = disconnect()
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.GET_SAVED_NETWORKS.value:
                ret = getSavedNetworks()
                localResponse.append_int32(0)
                localResponse.append_string16(ret or "{}")
            elif code == Transaction.SAVE_NETWORK.value:
                ssid = reader.read_string16()
                status, security = reader.read_int32()
                passphrase = reader.read_string16()
                ret = saveNetwork(ssid, security, passphrase)
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.FORGET_NETWORK.value:
                name = reader.read_string16()
                ret = forgetNetwork(name)
                localResponse.append_int32(0)
                localResponse.append_bool(ret)
            elif code == Transaction.GET_FACTORY_MAC_ADDRESSES.value:
                ret = getFactoryMacAddresses()
                localResponse.append_int32(0)
                localResponse.append_string16(ret or "{}")
            elif code == Transaction.GET_DHCP_INFO.value:
                ret = getDhcpInfo()
                localResponse.append_int32(0)
                localResponse.append_string16(ret or "{}")
            else:
                logging.error("{} unknown code: {}".format(INTERFACE, code))
                localResponse.append_int32(0)
                localResponse.append_int32(0)
        except Exception as e:
            logging.error("{} handler error on {}: {}".format(INTERFACE, code, e))
            localResponse = response.new_reply()
            localResponse.append_int32(0)
            localResponse.append_int32(0)
        return localResponse, 0

    def binderPresence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(SERVICE_NAME, status))
                args.wifiLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, responseHandler)
    args.wifiLoop = GLib.MainLoop()
    binderPresence()
    status = serviceManager.add_presence_handler(binderPresence)
    if status:
        args.wifiLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))
