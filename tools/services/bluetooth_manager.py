# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
import gbinder
from typing import Dict, Callable, Optional
from enum import Enum
import json

from tools.interfaces import IBluetooth
from tools.services.bluetooth_dbus_backend import BluezBackend

initData = {
    'controller': None,
    'stopping': False
}

callbackData = {
    'INTERFACE': "android.openfde.IBluetoothCallback",
    'lock': threading.Lock(),
    'registeredCallbacks': [],
    'deathNotifications': {}
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
                logging.verbose(f"Callback removed ({reason}). Remaining: {len(callbackData['registeredCallbacks'])}")
                ret = True

            if callback in callbackData['deathNotifications']:
                deathNotificationId = callbackData['deathNotifications'].pop(callback)
                try:
                    callback.remove_handler(deathNotificationId)
                    logging.verbose(f"Death notification cleaned up for: {callback}")
                except Exception as e:
                    logging.error(f"Failed to remove death notification: {e}")
            return ret

    def registerCallback(callback):
        logging.verbose("registerCallback: {}".format(callback))
        def deathHandler():
            removeCallback(callback, "clientDied")
            logging.verbose(f"Death notification received for callback: {callback}")

        global callbackData
        if callback:
            with callbackData['lock']:
                callbackData['registeredCallbacks'].append(callback)
                logging.verbose(f"Callback registered. Total callbacks: {len(callbackData['registeredCallbacks'])}")
                try:
                    deathNotificationId = callback.add_death_handler(deathHandler)
                    callbackData['deathNotifications'][callback] = deathNotificationId
                    logging.verbose(f"Death notification set up for callback: {callback}")
                except Exception as e:
                    logging.error(f"Failed to set up death notification: {e}")
                    logging.error("Continuing without death notification, will rely on broadcast error handling")
                return True
        else:
            logging.warning("DEBUG: No callback object received")
            return False

    def unregisterCallback(callback):
        return removeCallback(callback, "clientUnregistered") if callback else False

    def triggerEvent(what, data=""):
        logging.verbose(f"Triggering event: {what}, data: {data}")
        global callbackData
        with callbackData['lock']:
            callbacks = callbackData['registeredCallbacks'].copy()
        for i, callback in enumerate(callbacks):
            try:
                logging.verbose(f"DEBUG: Processing callback {i+1}/{len(callbacks)}: {callback}")
                if not callback.is_dead():
                    callbackClient = gbinder.Client(callback, callbackData['INTERFACE'])
                    request = callbackClient.new_request()
                    request.append_int32(what)
                    request.append_string16(data)
                    logging.verbose(f"DEBUG: Sending callback transaction to {callback}")
                    try:
                        status = callbackClient.transact_sync_oneway(Transaction.ON_EVENT.value, request)
                        logging.verbose(f"DEBUG: Callback oneway sent to {callback}, status={status}")
                    except Exception as e:
                        logging.error(f"DEBUG: Callback oneway failed for {callback}: {e}")
                        status = 1
                    if status:
                        logging.warning(f"Failed to send callback to {callback}, marking as dead")
                else:
                    logging.warning(f"Callback {callback} is dead, skipping")
            except Exception as e:
                logging.error(f"Error broadcasting to callback {callback}: {e}")
        logging.verbose(f"DEBUG: Sync broadcast completed")

    def onBackendEvent(what: int, data) -> None:
        if isinstance(data, dict):
            triggerEvent(int(what), json.dumps(data))
        else:
            triggerEvent(int(what), data or "")

    def init() -> bool:
        if initData['controller']:
            initData['controller'].getAdapterProperties()
        return True

    def cleanup():
        pass

    def enable() -> bool:
        return initData['controller'].powerOn()

    def disable() -> bool:
        return initData['controller'].powerOff()

    def getAdapterProperties() -> bool:
        return initData['controller'].getAdapterProperties()

    def getAdapterProperty(type: int) -> bool:
        return initData['controller'].getAdapterProperty(type)

    def setAdapterProperty(type: int, val: str) -> bool:
        return initData['controller'].setAdapterProperty(type, val)

    def createBond(address: str, addressType: int, transport: int) -> bool:
        return initData['controller'].createBond(address, addressType, transport)

    def removeBond(address: str) -> bool:
        return initData['controller'].removeBond(address)

    def cancelBond(address: str) -> bool:
        return initData['controller'].cancelBond(address)

    def pairingIsBusy() -> bool:
        return initData['controller'].pairingIsBusy()

    def getConnectionState(address: str) -> int:
        return initData['controller'].getConnectionState(address)

    def startDiscovery():
        return initData['controller'].startDiscovery()

    def cancelDiscovery() -> bool:
        return initData['controller'].cancelDiscovery()

    def connect(address: str) -> bool:
        return initData['controller'].connect(address)

    def disconnect(address: str) -> bool:
        return initData['controller'].disconnect(address)

    def setDeviceProperty(address: str, type: int, val: str) -> bool:
        return initData['controller'].setDeviceProperty(address, type, val)

    def isEnabled() -> bool:
        return initData['controller'].isEnabled()

    def sspReply(address: str, type: int, accept: bool, passkey: int) -> bool:
        return initData['controller'].sspReply(address, type, accept, passkey)

    def pinReply(address: str, accept: bool, pin: str) -> bool:
        return initData['controller'].pinReply(address, accept, pin)

    def getAdapterName() -> str:
        return initData['controller'].getAdapterName()

    def serviceThread():
        global initData
        while not initData['stopping']:
            if not initData['controller']:
                initData['controller'] = BluezBackend(onEvent=onBackendEvent)
                logging.verbose("Bluetooth: BluezBackend(D-Bus) has created")
            IBluetooth.addService(args, registerCallback, unregisterCallback, init,
                cleanup, enable, disable, getAdapterProperties, getAdapterProperty,
                setAdapterProperty, createBond, removeBond, cancelBond, pairingIsBusy,
                getConnectionState, startDiscovery, cancelDiscovery, connect, disconnect,
                setDeviceProperty, isEnabled, sspReply, pinReply, getAdapterName)

    initData['stopping'] = False
    args.bluetoothManager = threading.Thread(target=serviceThread)
    args.bluetoothManager.start()

def stop(args):
    global initData
    initData['stopping'] = True
    if initData['controller']:
        initData['controller'].cleanup()
    try:
        if args.bluetoothLoop:
            args.bluetoothLoop.quit()
    except AttributeError:
        logging.debug("bluetooth service is not even started")
