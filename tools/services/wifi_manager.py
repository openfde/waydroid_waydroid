# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import threading
from enum import Enum
import gbinder
from tools.interfaces import IWifi
from tools.services.wifi_dbus_backend import NMWifiBackend

initData = {
    'controller': None,
    'stopping': False,
    'onlyStatus': True,
}

callbackData = {
    'INTERFACE': "android.openfde.IWifiCallback",
    'lock': threading.Lock(),
    'registeredCallbacks': [],
    'deathNotifications': {},
}

def start(args):
    class Transaction(Enum):
        ON_EVENT = 1

    def removeCallback(callback, reason="unknown"):
        global callbackData
        with callbackData['lock']:
            ret = False
            if callback in callbackData['registeredCallbacks']:
                callbackData['registeredCallbacks'].remove(callback)
                logging.verbose(
                    f"Wifi callback removed ({reason}). Remaining: "
                    f"{len(callbackData['registeredCallbacks'])}")
                ret = True
            if callback in callbackData['deathNotifications']:
                deathNotificationId = callbackData['deathNotifications'].pop(callback)
                try:
                    callback.remove_handler(deathNotificationId)
                except Exception as e:
                    logging.error(f"Failed to remove death notification: {e}")
            return ret

    def registerCallback(callback):
        def deathHandler():
            removeCallback(callback, "clientDied")

        global callbackData
        if callback:
            with callbackData['lock']:
                callbackData['registeredCallbacks'].append(callback)
                try:
                    deathNotificationId = callback.add_death_handler(deathHandler)
                    callbackData['deathNotifications'][callback] = deathNotificationId
                except Exception as e:
                    logging.error(f"Failed to set up death notification: {e}")
                    logging.error("Continue without death notification")
            return True
        return False

    def unregisterCallback(callback):
        return removeCallback(callback, "clientUnregistered") if callback else False

    def triggerEvent(what, data=""):
        global callbackData
        with callbackData['lock']:
            callbacks = callbackData['registeredCallbacks'].copy()
        for callback in callbacks:
            try:
                if callback.is_dead():
                    continue
                callbackClient = gbinder.Client(callback, callbackData['INTERFACE'])
                request = callbackClient.new_request()
                request.append_int32(what)
                request.append_string16(data)
                callbackClient.transact_sync_oneway(Transaction.ON_EVENT.value, request)
            except Exception as e:
                logging.error(f"Wifi triggerEvent({what}) to callback fail: {e}")

    def onBackendEvent(what, data):
        triggerEvent(what, data or "")

    def serviceThread():
        global initData
        initData['controller'] = NMWifiBackend(onEvent=onBackendEvent)

        def init():
            controller = initData['controller']
            if controller is None:
                return False
            try:
                for what, data in controller.currentStateEvents():
                    triggerEvent(what, json.dumps(data, ensure_ascii=False))
                return True
            except Exception as e:
                logging.error(f"Wifi init: initial-state trigger fail: {e}")
                return False

        def isEnabled():
            return initData['controller'].isEnabled()

        def setEnabled(on):
            return True if initData['onlyStatus'] else initData['controller'].setEnabled(on)

        def startScan():
            return initData['controller'].startScan()

        def getConnectionInfo():
            return initData['controller'].getConnectionInfo()

        def getScanResults():
            return initData['controller'].getScanResults()

        def connect(ssid, security, passphrase):
            return True if initData['onlyStatus'] else initData['controller'].connect(ssid, int(security), passphrase)

        def connectSaved(name):
            return True if initData['onlyStatus'] else initData['controller'].connectSaved(name)

        def disconnect():
            return True if initData['onlyStatus'] else initData['controller'].disconnect()

        def getSavedNetworks():
            return initData['controller'].getSavedNetworks()

        def saveNetwork(ssid, security, passphrase):
            return True if initData['onlyStatus'] else initData['controller'].saveNetwork(ssid, int(security), passphrase)

        def forgetNetwork(name):
            return True if initData['onlyStatus'] else initData['controller'].forgetNetwork(name)

        def getFactoryMacAddresses():
            return initData['controller'].getFactoryMacAddresses()

        def getDhcpInfo():
            return initData['controller'].getDhcpInfo()

        IWifi.addService(args, registerCallback, unregisterCallback, init, isEnabled,
                         setEnabled, startScan, getConnectionInfo, getScanResults,
                         connect, connectSaved, disconnect, getSavedNetworks,
                         saveNetwork, forgetNetwork, getFactoryMacAddresses,
                         getDhcpInfo)

    initData['stopping'] = False
    args.wifiManager = threading.Thread(target=serviceThread, daemon=True)
    args.wifiManager.start()

def stop(args):
    global initData
    initData['stopping'] = True
    if initData['controller']:
        initData['controller'].cleanup()
        initData['controller'] = None
    with callbackData['lock']:
        callbackData['registeredCallbacks'].clear()
        callbackData['deathNotifications'].clear()
    try:
        if args.wifiLoop:
            args.wifiLoop.quit()
    except AttributeError:
        logging.debug("wifi service is not even started")
