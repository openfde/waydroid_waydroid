# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
import time
import gbinder
import subprocess
import re
import queue
from typing import List, Dict, Optional, Callable
from enum import Enum
import json

from tools.interfaces import IBluetooth

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

patterns = {
    'poweredOn': re.compile(r'Powered:\s+yes'),
    'poweredOff': re.compile(r'Powered:\s+no'),
    'scanOn': re.compile(r'Discovering:\s+yes'),
    'scanOff': re.compile(r'Discovering:\s+no'),
    'controllerAliased': re.compile(r'Alias:\s+.*'),
    'controllerPairable': re.compile(r'Pairable:\s+yes'),
    'controllerDisPairable': re.compile(r'Pairable:\s+no'),
    'deviceConnected': re.compile(r'Connected:\s+yes'),
    'deviceDisconnected': re.compile(r'Connected:\s+no'),
    'devicePaired': re.compile(r'Paired:\s+yes'),
    'deviceAliased': re.compile(r'Alias:\s+.*'),
    'mac': re.compile(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})'),
    'ansi': re.compile(r'\x1b\[[0-9;]*[mK]|\x1b\][0-9];.*?\x07|\x1b[=>\?].|\x1b.', re.VERBOSE),
    'ascii': re.compile(r'[\x00-\x1f\x7f-\x9f]'),
    'starsWithMac': re.compile(r'^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$'),
    'deiceMacInfo': re.compile(r'Device\s+([0-9A-F:]+)\s+(.+)'),
    'deviceNewChgDel': r'\[(NEW|CHG|DEL)\]\s+Device\s+([0-9A-F:]+)\s*(.*)',
    'ControllerNewChgDel': r'\[(NEW|CHG|DEL)\]\s+Controller\s+([0-9A-F:]+)\s*(.*)',
    'UUIDs': r'\(([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\)',
    'agent': r'\[agent\]\s+Passkey:\s+([0-9]+)',
    'pairing': r'Attempting to pair with\s+([0-9A-F:]+)',
    'devices': r'Device\s+([0-9A-F:]+)\s*(.*)'
}

def start(args):
    class Transaction(Enum):
        ON_EVENT = 1

    class ScanMode(Enum):
        BT_SCAN_MODE_NONE = 0
        BT_SCAN_MODE_CONNECTABLE = 1
        BT_SCAN_MODE_CONNECTABLE_DISCOVERABLE = 2

    class ConnectionState(Enum):
        STATE_DISCONNECTED = 0
        STATE_CONNECTING = 1
        STATE_CONNECTED = 2
        STATE_DISCONNECTING = 3

    class BondState(Enum):
        BT_BOND_STATE_NONE = 0
        BT_BOND_STATE_BONDING = 1
        BT_BOND_STATE_BONDED = 2

    class BluetoothProperty(Enum):
        BT_PROPERTY_BDNAME = 0x01
        BT_PROPERTY_BDADDR = 0x02
        BT_PROPERTY_UUIDS = 0x03
        BT_PROPERTY_CLASS_OF_DEVICE = 0x04
        BT_PROPERTY_TYPE_OF_DEVICE = 0x05
        BT_PROPERTY_SERVICE_RECORD = 0x06
        BT_PROPERTY_ADAPTER_SCAN_MODE = 0x07
        BT_PROPERTY_ADAPTER_BONDED_DEVICES = 0x08
        BT_PROPERTY_ADAPTER_DISCOVERABLE_TIMEOUT = 0x09
        BT_PROPERTY_REMOTE_FRIENDLY_NAME = 0x0A
        BT_PROPERTY_REMOTE_RSSI = 0x0B
        BT_PROPERTY_REMOTE_VERSION_INFO = 0x0C
        BT_PROPERTY_LOCAL_LE_FEATURES = 0x0D
        BT_PROPERTY_DYNAMIC_AUDIO_BUFFER = 0x10
        BT_PROPERTY_REMOTE_IS_COORDINATED_SET_MEMBER = 0x11
        BT_PROPERTY_WL_MEDIA_PLAYERS_LIST = 0x14;
        BT_PROPERTY_REMOTE_ASHA_CAPABILITY = 0X15
        BT_PROPERTY_REMOTE_ASHA_TRUNCATED_HISYNCID = 0X16
        BT_PROPERTY_REMOTE_MODEL_NUM = 0x17
        BT_PROPERTY_LOCAL_IO_CAPS = 0x0e

    class CallBackEvents(Enum):
        BT_STATE_ON = 0
        BT_STATE_OFF = 1
        BT_DISCOVERY_STARTED = 2
        BT_DISCOVERY_STOPPED = 3
        ADAPTER_PROPERTY_CHANGED = 4
        DEVICE_FOUND = 5
        DEVICE_PROPERTY_CHANGED = 6
        BOND_STATE_CHANGE = 7
        FROFILE_CONNECTION_STATE_CHANGED = 8
        PIN_REQUEST = 9
        AGENT = 998
        DEVICE_REMOVED = 999
        All_CHG = 1000

    class Device(Enum):
        BITMASK = 0x1FFC
        PERIPHERAL_KEYBOARD = 0x0540

    def haveHci() -> bool:
        result = subprocess.run(['hciconfig'], capture_output=True, text=True, timeout=10)
        return True if 'BD Address:' in result.stdout else False

    def threadTodo(event, delay, data):
        def delayTodo(event, delay, data):
            time.sleep(delay)
            triggerEvent(event, data)
        threading.Thread(target=delayTodo, args=(event, delay, data)).start()

    class BluetoothEvent:
        def __init__(self, eventType: CallBackEvents, data: Dict = None):
            self.eventType = eventType
            self.data = data or {}
            self.timestamp = time.time()

    class BluetoothEventMonitor:
        def __init__(self, controller):
            self.controller = controller
            self.process = None
            self.monitoring = False
            self.eventHandlers = {}
            self.eventQueue = queue.Queue()
            self.monitorThread = None
            self._lock = threading.Lock()
            self.knownDevices = set()

        def registerHandler(self, eventType: CallBackEvents, handler: Callable):
            with self._lock:
                self.eventHandlers[eventType] = handler

        def unregisterHandler(self, eventType: CallBackEvents, handler: Callable):
            with self._lock:
                self.eventHandlers[eventType] = None

        def startMonitoring(self):
            if (not haveHci()) or self.monitoring:
                logging.verbose("monitoring has running")
                return False
            try:
                self.process = subprocess.Popen(
                    ['bluetoothctl'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                self.monitoring = True
                self.monitorThread = threading.Thread(target=self._monitorOutput, daemon=True)
                self.monitorThread.start()

                dispatchThread = threading.Thread(target=self._dispatchEvents, daemon=True)
                dispatchThread.start()
                logging.verbose("monitoring to runn")
                return True
            except Exception as e:
                logging.error(f"start monitoring fail: {e}")
                self.monitoring = False
                return False

        def stopMonitoring(self):
            if not self.monitoring:
                return
            logging.verbose("to stop monitoring...")
            self.monitoring = False
            if self.process:
                try:
                    self.process.stdin.write('quit\n')
                    self.process.stdin.flush()
                    time.sleep(0.5)
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    try:
                        self.process.kill()
                    except:
                        pass
                self.process = None
            if self.monitorThread:
                self.monitorThread.join(timeout=2)
            logging.verbose("monitoring stoped")

        def _monitorOutput(self):
            try:
                while self.monitoring and self.process:
                    line = self.process.stdout.readline()
                    if not line:
                        break
                    line = patterns['ansi'].sub('', line)
                    line = patterns['ascii'].sub('', line)
                    line.rstrip('\n')
                    if not line:
                        continue
                    if (line.startswith('[NEW]') or line.startswith('[CHG]') or line.startswith('[DEL]')
                        or line.startswith('[agent]')):
                        event = self._parseEventLine(line)
                        if event:
                            self.eventQueue.put(event)
                    elif "(yes/no):" in line:
                        self.sendCommand('yes')
                    elif "Attempting to pair with" in line:
                        match = re.search(patterns['pairing'], line)
                        mac = match.group(1)
                        if mac in self.knownDevices:
                            self.controller.devices[mac]['Pairing'] = True
            except Exception as e:
                if self.monitoring:
                    logging.error(f"monitorOutput thread fail : {e}")

        def _parseEventLine(self, line: str) -> Optional[BluetoothEvent]:
            eventTypeHead = None
            if line.startswith('[NEW]'):
                eventTypeHead = 'NEW'
            elif line.startswith('[CHG]'):
                eventTypeHead = 'CHG'
            elif line.startswith('[DEL]'):
                eventTypeHead = 'DEL'
            elif line.startswith('[agent]'):
                logging.debug("agent line: " + line)
                match = re.search(patterns['agent'], line)
                if match:
                    pairingMac = "none"
                    for mac in self.controller.devices:
                        if (('Pairing' in self.controller.devices[mac] and self.controller.devices[mac]['Pairing'] == True) and
                            ((Device.BITMASK.value & int(self.controller.devices[mac]['Class'], 16)) == Device.PERIPHERAL_KEYBOARD.value)):
                            pairingMac = mac
                            break
                    if pairingMac != "none":
                        return BluetoothEvent(
                            CallBackEvents.AGENT,
                            {
                                'subType': CallBackEvents.PIN_REQUEST,
                                'mac': pairingMac,
                                'name': self.controller.devices[mac]['Name'],
                                'pin': int(match.group(1))
                            }
                        )
                return None
            else:
                return None
            match = re.search(patterns['deviceNewChgDel'], line)
            isController = False
            if not match:
                match = re.search(patterns['ControllerNewChgDel'], line)
                if not match:
                    return None
                isController = True

            mac = match.group(2)
            deviceInfo = match.group(3).strip()

            if not deviceInfo:
                return None
            if eventTypeHead == 'NEW':
                if patterns['starsWithMac'].match(deviceInfo):
                    return None
                self.knownDevices.add(mac)
                logging.verbose(f"note a device: {mac} - {deviceInfo}")
                infoOutput = self.controller.sendCommand('info ' + mac)
                return BluetoothEvent(
                    CallBackEvents.DEVICE_FOUND,
                    {
                        'mac': mac,
                        'name': deviceInfo
                    }
                )
            elif eventTypeHead == 'DEL':
                if mac not in self.knownDevices:
                    return None
                return BluetoothEvent(
                    CallBackEvents.DEVICE_REMOVED,
                    {
                        'mac': mac,
                        'name': deviceInfo
                    }
                )
            elif eventTypeHead == 'CHG':  
                if (mac not in self.knownDevices) and (not isController):
                    return None
                return BluetoothEvent(
                    CallBackEvents.All_CHG,
                    {
                        'controller': isController,
                        'mac': mac,
                        'data': deviceInfo
                    }
                )
            else:
                return None

        def _dispatchEvents(self):
            while self.monitoring:
                try:
                    event = self.eventQueue.get()
                    with self._lock:
                        handler = self.eventHandlers.get(event.eventType)
                        if handler:
                            try:
                                handler(event)
                            except Exception as e:
                                logging.error(f"event handle error: {e}")
                except queue.Empty:
                    continue
                except Exception as e:
                    if self.monitoring:
                        logging.error(f"dispatchEvents error: {e}")

        def sendCommand(self, command: str):
            if self.process and self.monitoring and haveHci():
                try:
                    self.process.stdin.write(command + '\n')
                    self.process.stdin.flush()
                    logging.verbose(f"stdinwrite: {command}")
                except Exception as e:
                    logging.error(f"sendCommand fail: {e}")

    class BluetoothController:
        def __init__(self):
            self.devices = {}
            self.controller = {}
            self.eventMonitor = BluetoothEventMonitor(self)
            self.monitoringEnabled = False
            if haveHci():
               infoOutput = self.sendCommand("show")
               uuids = re.findall(patterns['UUIDs'], infoOutput, re.IGNORECASE)
               self.controller['UUIDs'] = ''.join([uuid.replace('-', '') for uuid in uuids])
               for line in infoOutput.split('\n'):
                   line = line.strip()
                   if 'Controller ' in line:
                       match = re.search(patterns['mac'], line)
                       if match:
                           self.controller['mac'] = match.group(1)
                   elif 'Name:' in line:
                       self.controller['name'] = line.split(':', 1)[1].strip()
                   elif 'Alias:' in line:
                       self.controller['alias'] = line.split(':', 1)[1].strip()
                   elif 'Class:' in line:
                       self.controller['class'] = line.split(':', 1)[1].strip()
                   elif 'Powered:' in line:
                       self.controller['Powered'] = 'yes' in line
                   elif 'Discoverable:' in line:
                       self.controller['Discoverable'] = 'yes' in line
                   elif 'Pairable:' in line:
                       self.controller['Pairable'] = 'yes' in line
                   elif 'Discovering:' in line:
                       self.controller['Discovering'] = 'yes' in line
            else:
                self.controller = {
                    'alias': 'OpenFDE',
                    'mac': '11:22:33:44:55:66',
                    'class': '0x00000000',
                    'Pairable': False,
                    'Discoverable': False
                }

        def sendCommand(self, command: str) -> str:
            if not haveHci():
                return "noController"
            try:
                result = subprocess.run('bluetoothctl ' + command, shell=True, capture_output=True, text=True, timeout=5)
                logging.verbose(f"sendCommand: bluetoothctl {command}")
                return result.stdout.strip()
            except subprocess.TimeoutExpired:
                return "TimeoutExpired"
            except Exception as e:
                return f"sendCommand fail：{e}"

        def startDiscovery(self):
            info = self.sendCommand("show")
            if "Discovering: yes" in info:
                self.controller['Discovering'] = True
                triggerEvent(CallBackEvents.BT_DISCOVERY_STARTED.value)
                info = self.sendCommand("devices")
                offset = 1
                for line in info.split('\n'):
                   line = line.strip()
                   match = re.search(patterns['devices'], line)
                   name = match.group(2).strip() if match else None
                   if match and not patterns['starsWithMac'].match(name):
                       mac = match.group(1)
                       self.eventMonitor.knownDevices.add(mac)
                       deviceInfo = self.sendCommand("info " + mac)
                       deviceClass = '0x00000000'
                       for line in deviceInfo.split('\n'):
                          if 'Class:' in line:
                              deviceClass = line.split()[1].strip()
                              break
                       triggerEvent(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, json.dumps({
                           'mac': mac,
                           BluetoothProperty.BT_PROPERTY_BDADDR.value: mac,
                           BluetoothProperty.BT_PROPERTY_CLASS_OF_DEVICE.value: deviceClass,
                           BluetoothProperty.BT_PROPERTY_BDNAME.value: name
                       }))
                       threadTodo(CallBackEvents.DEVICE_FOUND.value, 0.1 * offset, json.dumps({'mac': mac}))
                       offset += 1
                       self.devices[mac] = {
                           'Name': name,
                           'Class': deviceClass,
                           'Paired': False,
                           'Connected': False
                       }
            else:
                self.sendMonitorCommand("scan on")
            return True

        def cancelDiscovery(self):
            info = self.sendCommand("show")
            if "Discovering: no" in info:
                self.controller['Discovering'] = False
                triggerEvent(CallBackEvents.BT_DISCOVERY_STOPPED.value)
            else:
                self.sendMonitorCommand("scan off")
            return True

        def triggerPairedAndConnectedDevices(self):
            info = self.sendCommand("paired-devices")
            for line in info.split('\n'):
                line = line.strip()
                match = re.search(patterns['deiceMacInfo'], line)
                if match:
                    mac = match.group(1)
                    name = match.group(2)
                    self.eventMonitor.knownDevices.add(mac)
                    logging.verbose(f"knownDevices: {mac} - {name}")
                    deviceClass = '0x00000000'
                    deviceInfo = self.sendCommand("info " + mac)
                    for oneLine in deviceInfo.split('\n'):
                       if 'Class:' in oneLine:
                           deviceClass = oneLine.split()[1].strip()
                           break
                    uuids = re.findall(patterns['UUIDs'], deviceInfo, re.IGNORECASE)
                    self.devices[mac] = {
                        'Name': name,
                        'Class': deviceClass,
                        'Paired': True,
                        'Connected': 'Connected: yes' in deviceInfo
                    }
                    if self.devices[mac]['Connected']:
                        threadTodo(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, 0.1, json.dumps({
                            'mac': mac,
                            BluetoothProperty.BT_PROPERTY_BDADDR.value: mac,
                            BluetoothProperty.BT_PROPERTY_BDNAME.value: name,
                            BluetoothProperty.BT_PROPERTY_CLASS_OF_DEVICE.value: deviceClass,
                            BluetoothProperty.BT_PROPERTY_UUIDS.value: ''.join([uuid.replace('-', '') for uuid in uuids])
                        }))
                        threadTodo(CallBackEvents.DEVICE_FOUND.value, 0.2, json.dumps({
                           'mac': mac
                        }))
                        threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.3, json.dumps({
                            'mac': mac,
                            'state': BondState.BT_BOND_STATE_BONDING.value
                        }))
                        threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.4, json.dumps({
                           'mac': mac,
                           'state': BondState.BT_BOND_STATE_BONDED.value
                        }))
                        threadTodo(CallBackEvents.FROFILE_CONNECTION_STATE_CHANGED.value, 0.5, json.dumps({
                           'mac': mac,
                           'state': ConnectionState.STATE_CONNECTED.value
                        }))
                        logging.verbose(f"has connected device: {mac} - {name}")
                    else:
                        threadTodo(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, 0.1, json.dumps({
                            'mac': mac,
                            BluetoothProperty.BT_PROPERTY_BDADDR.value: mac,
                            BluetoothProperty.BT_PROPERTY_BDNAME.value: name,
                            BluetoothProperty.BT_PROPERTY_CLASS_OF_DEVICE.value: deviceClass,
                            BluetoothProperty.BT_PROPERTY_UUIDS.value: ''.join([uuid.replace('-', '') for uuid in uuids])
                        }))
                        threadTodo(CallBackEvents.DEVICE_FOUND.value, 0.2, json.dumps({
                           'mac': mac
                        }))
                        threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.3, json.dumps({
                            'mac': mac,
                            'state': BondState.BT_BOND_STATE_BONDING.value
                        }))
                        threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.4, json.dumps({
                           'mac': mac,
                           'state': BondState.BT_BOND_STATE_BONDED.value
                        }))
                        logging.verbose(f"has paired device: {mac} - {name}")

        def powerOn(self) -> bool:
            info = self.sendCommand("show")
            if "Powered: no" in info:
                self.sendMonitorCommand("power on")
            else:
                triggerEvent(CallBackEvents.BT_STATE_ON.value)
                self.triggerPairedAndConnectedDevices()
            return True

        def powerOff(self) -> bool:
            info = self.sendCommand("show")
            if "Powered: yes" in info:
                self.sendMonitorCommand("power off")
            else:
                triggerEvent(CallBackEvents.BT_STATE_OFF.value)
                self.devices = {}
            return True

        def pairingIsBusy(self) -> bool:
            return False

        def getConnectionState(self, address: str) -> int:
            return ConnectionState.STATE_CONNECTED.value if address in self.devices and self.devices[address]['Connected'] else ConnectionState.STATE_DISCONNECTED.value 

        def createBond(self, address: str, addressType: int, transport: int) -> bool:
            if self.devices[address]['Paired']:
                deviceInfo = self.sendCommand("info " + address)
                uuids = re.findall(patterns['UUIDs'], deviceInfo, re.IGNORECASE)
                triggerEvent(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, json.dumps({
                    'mac': address,
                    BluetoothProperty.BT_PROPERTY_UUIDS.value: ''.join([uuid.replace('-', '') for uuid in uuids])
                }))
                threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.1, json.dumps({
                    'mac': address,
                    'state': BondState.BT_BOND_STATE_BONDING.value
                }))
                threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.2, json.dumps({
                    'mac': address,
                    'state': BondState.BT_BOND_STATE_BONDED.value
                }))
            else:
                triggerEvent(CallBackEvents.BOND_STATE_CHANGE.value, json.dumps({
                    'mac': address,
                    'state': BondState.BT_BOND_STATE_BONDING.value
                }))
                self.sendMonitorCommand("trust " + address)
                self.sendMonitorCommand("pair " + address)
                def delayTodo(delay, address):
                    time.sleep(delay)
                    if not self.devices[address]['Paired']:
                        logging.debug("not paired")
                        triggerEvent(CallBackEvents.BOND_STATE_CHANGE.value, json.dumps({
                            'mac': address,
                            'state': BondState.BT_BOND_STATE_NONE.value
                        }))
                threading.Thread(target=delayTodo, args=(30, address)).start()
            return True

        def removeBond(self, address: str) -> bool:
            if self.devices[address]['Paired']:
                self.sendMonitorCommand("remove " + address)
            else:
                triggerEvent(CallBackEvents.BOND_STATE_CHANGE.value, json.dumps({
                    'mac': address,
                    'state': BondState.BT_BOND_STATE_NONE.value
                }))
            return True

        def cancelBond(self, address: str) -> bool:
            return removeBond(address)

        def getAdapterProperties() -> bool:
            return True

        def getAdapterProperty(self, type: int) -> bool:
            def getAdapterName() -> bool:
                triggerEvent(CallBackEvents.ADAPTER_PROPERTY_CHANGED.value,
                    json.dumps({BluetoothProperty.BT_PROPERTY_BDNAME.value: self.controller['alias']}))
                return True

            def adapterAddress() -> bool:
                triggerEvent(CallBackEvents.ADAPTER_PROPERTY_CHANGED.value,
                    json.dumps({BluetoothProperty.BT_PROPERTY_BDADDR.value: self.controller['mac']}))
                return True

            def adapterClass() -> bool:
                data = {}
                data[BluetoothProperty.BT_PROPERTY_CLASS_OF_DEVICE.value] = self.controller['class']
                scanMode = ScanMode.BT_SCAN_MODE_NONE.value
                if initData['controller'].controller['Discoverable'] and initData['controller'].controller['Pairable']:
                    scanMode = ScanMode.BT_SCAN_MODE_CONNECTABLE_DISCOVERABLE.value
                elif initData['controller'].controller['Pairable']:
                    scanMode = ScanMode.BT_SCAN_MODE_CONNECTABLE.value
                data[BluetoothProperty.BT_PROPERTY_ADAPTER_SCAN_MODE.value] = scanMode
                triggerEvent(CallBackEvents.ADAPTER_PROPERTY_CHANGED.value, json.dumps(data))
                return True

            def getLocalIoCaps() -> bool:
                return True

            def dynamicAudioBuffer() -> bool:
                return True

            def adapterUuids() -> bool:
                triggerEvent(CallBackEvents.ADAPTER_PROPERTY_CHANGED.value,
                    json.dumps({BluetoothProperty.BT_PROPERTY_UUIDS.value: self.controller['UUIDs']}))
                return True

            def adapterBondedDevices() -> bool:
                device_list = [
                    mac
                    for mac, value in self.devices.items()
                    if value.get('Paired', False)
                ]
                triggerEvent(CallBackEvents.ADAPTER_PROPERTY_CHANGED.value,
                    json.dumps({BluetoothProperty.BT_PROPERTY_ADAPTER_BONDED_DEVICES.value: " ".join(device_list)}))
                return True

            handlerMap = {
                BluetoothProperty.BT_PROPERTY_BDNAME.value: getAdapterName,
                BluetoothProperty.BT_PROPERTY_BDADDR.value: adapterAddress,
                BluetoothProperty.BT_PROPERTY_CLASS_OF_DEVICE.value: adapterClass,
                BluetoothProperty.BT_PROPERTY_LOCAL_IO_CAPS.value: getLocalIoCaps,
                BluetoothProperty.BT_PROPERTY_DYNAMIC_AUDIO_BUFFER.value: dynamicAudioBuffer,
                BluetoothProperty.BT_PROPERTY_UUIDS.value: adapterUuids,
                BluetoothProperty.BT_PROPERTY_ADAPTER_BONDED_DEVICES.value: adapterBondedDevices,
            }
            handler = handlerMap.get(type)
            return handler() if handler else False

        def setAdapterProperty(self, type: int, val: str) -> bool:
            def setAdapterName(name: str) -> bool:
                self.sendMonitorCommand("system-alias " + name)
                return True

            def setLocalIoCaps(val: str) -> bool:
                return True

            def setAdapterScanMode(mode: str) -> bool:
                if ScanMode.BT_SCAN_MODE_CONNECTABLE_DISCOVERABLE.value == int(mode):
                    if not self.controller['Discoverable']:
                        self.sendMonitorCommand("discoverable on")
                    if not self.controller['Pairable']:
                        self.sendMonitorCommand("pairable on")
                elif ScanMode.BT_SCAN_MODE_CONNECTABLE.value == int(mode):
                    if not self.controller['Pairable']:
                        self.sendMonitorCommand("pairable on")
                    if self.controller['Discoverable']:
                        self.sendMonitorCommand("discoverable off")
                elif ScanMode.BT_SCAN_MODE_NONE.value == int(mode):
                    if self.controller['Discoverable']:
                        self.sendMonitorCommand("discoverable off")
                    if self.controller['Pairable']:
                        self.sendMonitorCommand("pairable off")
                else:
                    logging.error("unkown mode!!")
                return True

            def setAdapterDiscoverableTimeout(val: str) -> bool:
                def toDiscoverable(timeout):
                    for i in range(timeout):
                        time.sleep(1)
                    self.sendMonitorCommand("discoverable off")
                if int(val) > 0:
                    threading.Thread(target=toDiscoverable, args=(int(val),)).start()
                return True

            handlerMap = {
                BluetoothProperty.BT_PROPERTY_BDNAME.value: setAdapterName,
                BluetoothProperty.BT_PROPERTY_LOCAL_IO_CAPS.value: setLocalIoCaps,
                BluetoothProperty.BT_PROPERTY_ADAPTER_SCAN_MODE.value: setAdapterScanMode,
                BluetoothProperty.BT_PROPERTY_ADAPTER_DISCOVERABLE_TIMEOUT.value: setAdapterDiscoverableTimeout,
            }
            handler = handlerMap.get(type)
            return handler(val) if handler else False

        def connect(self, address: str) -> bool:
            if self.devices[address]['Connected']:
                triggerEvent(CallBackEvents.FROFILE_CONNECTION_STATE_CHANGED.value, json.dumps({
                    'mac': address,
                    'state': ConnectionState.STATE_CONNECTED.value
                }))
            else:
                self.sendMonitorCommand("connect " + address)
            return True

        def disconnect(self, address: str) -> bool:
            if self.devices[address]['Connected']:
                self.sendMonitorCommand("disconnect " + address)
            else:
                triggerEvent(CallBackEvents.FROFILE_CONNECTION_STATE_CHANGED.value, json.dumps({
                    'mac': address,
                    'state': ConnectionState.STATE_DISCONNECTED.value
                }))
            return True

        def setDeviceProperty(self, address: str, type: int, val: str) -> bool:
            def setDeviceName(address: str, name: str) -> bool:
                if self.devices[address]['Connected']:
                    self.sendMonitorCommand("set-alias " + name)
                return True

            handlerMap = {
                BluetoothProperty.BT_PROPERTY_REMOTE_FRIENDLY_NAME.value: setDeviceName         
            }
            handler = handlerMap.get(type)
            return handler(address, val) if handler else False

        def startMonitoring(self) -> bool:
            if self.eventMonitor.startMonitoring():
                self.monitoringEnabled = True
                return True
            return False

        def stopMonitoring(self):
            self.eventMonitor.stopMonitoring()
            self.monitoringEnabled = False   

        def onDeviceDiscovered(self, handler: Callable):
            self.eventMonitor.registerHandler(CallBackEvents.DEVICE_FOUND, handler)

        def onDeviceRemoved(self, handler: Callable):
            self.eventMonitor.registerHandler(CallBackEvents.DEVICE_REMOVED, handler)

        def onChg(self, handler: Callable):
            self.eventMonitor.registerHandler(CallBackEvents.All_CHG, handler)

        def sendMonitorCommand(self, command: str):
            if self.monitoringEnabled:
                self.eventMonitor.sendCommand(command)

        def cleanup(self):
            if self.monitoringEnabled:
                self.stopMonitoring()

        def onAgent(self, handler: Callable):
            self.eventMonitor.registerHandler(CallBackEvents.AGENT, handler)

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

    def triggerEvent(what, data = ""):
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

    def onDeviceDiscovered(event: BluetoothEvent):
        deviceClass = '0x00000000'
        deviceInfo = initData['controller'].sendCommand("info " + event.data['mac'])
        for line in deviceInfo.split('\n'):
           if 'Class:' in line:
               deviceClass = line.split()[1].strip()
               break
        triggerEvent(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, json.dumps({
            'mac': event.data['mac'],
            BluetoothProperty.BT_PROPERTY_BDADDR.value: event.data['mac'],
            BluetoothProperty.BT_PROPERTY_CLASS_OF_DEVICE.value: deviceClass,
            BluetoothProperty.BT_PROPERTY_BDNAME.value: event.data['name']
        }))
        threadTodo(CallBackEvents.DEVICE_FOUND.value, 0.1, json.dumps({'mac': event.data['mac']}))
        initData['controller'].devices[event.data['mac']] = {
            'Name': event.data['name'],
            'Class': deviceClass,
            'Paired': False,
            'Connected': False
        }

    def onDeviceRemoved(event: BluetoothEvent):
        triggerEvent(CallBackEvents.BOND_STATE_CHANGE.value, json.dumps({
           'mac': event.data['mac'],
           'state': BondState.BT_BOND_STATE_NONE.value
        }))
        initData['controller'].devices[event.data['mac']] = {
            'Paired': False,
            'Connected': False
        }

    def onChg(event: BluetoothEvent):
        if event.data['controller']:
            if patterns['poweredOn'].search(event.data['data']):
                initData['controller'].controller['Powered'] = True
                triggerEvent(CallBackEvents.BT_STATE_ON.value)
                initData['controller'].triggerPairedAndConnectedDevices()
            elif patterns['poweredOff'].search(event.data['data']):
                initData['controller'].controller['Powered'] = False
                triggerEvent(CallBackEvents.BT_STATE_OFF.value)
                initData['controller'].devices = {}
            elif patterns['scanOn'].search(event.data['data']):
                initData['controller'].controller['Discovering'] = True
                triggerEvent(CallBackEvents.BT_DISCOVERY_STARTED.value)
            elif patterns['scanOff'].search(event.data['data']):
                initData['controller'].controller['Discovering'] = False
                triggerEvent(CallBackEvents.BT_DISCOVERY_STOPPED.value)
            elif patterns['controllerAliased'].search(event.data['data']):
                initData['controller'].controller['alias'] = event.data['data'].split(':', 1)[1].strip()
                triggerEvent(CallBackEvents.ADAPTER_PROPERTY_CHANGED.value, json.dumps({
                    BluetoothProperty.BT_PROPERTY_BDNAME.value: event.data['data'].split(':', 1)[1].strip()
                }))
            elif patterns['controllerPairable'].search(event.data['data']):
                initData['controller'].controller['Pairable'] = True
            elif patterns['controllerDisPairable'].search(event.data['data']):
                initData['controller'].controller['Pairable'] = False
        else:
            if patterns['devicePaired'].search(event.data['data']):
                deviceInfo = initData['controller'].sendCommand("info " + event.data['mac'])
                uuids = re.findall(patterns['UUIDs'], deviceInfo, re.IGNORECASE)
                triggerEvent(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, json.dumps({
                    'mac': event.data['mac'],
                    BluetoothProperty.BT_PROPERTY_UUIDS.value: ''.join([uuid.replace('-', '') for uuid in uuids])
                }))
                threadTodo(CallBackEvents.BOND_STATE_CHANGE.value, 0.1, json.dumps({
                    'mac': event.data['mac'],
                    'state': BondState.BT_BOND_STATE_BONDED.value
                }))
                if event.data['mac'] in initData['controller'].devices:
                    initData['controller'].devices[event.data['mac']]['Paired'] = True
                    initData['controller'].devices[event.data['mac']]['Pairing'] = False
                else:
                    logging.debug(f"{event.data['mac']} paired but not in devices!!")
            elif patterns['deviceConnected'].search(event.data['data']):
                def delayTodo(event, delay, data):
                    logging.debug(f"delayTodo...e")
                    time.sleep(delay)
                    logging.debug(f"delayTodo...x")
                    if initData['controller'].devices[data['mac']]['Paired']:
                        triggerEvent(event, json.dumps(data))
                if initData['controller'].devices[event.data['mac']]['Paired']:
                    triggerEvent(CallBackEvents.FROFILE_CONNECTION_STATE_CHANGED.value, json.dumps({
                        'mac': event.data['mac'],
                        'state': ConnectionState.STATE_CONNECTED.value
                    }))
                else:
                    threading.Thread(target=delayTodo, args=(CallBackEvents.FROFILE_CONNECTION_STATE_CHANGED.value
                        , 0.2, {'mac': event.data['mac'], 'state': ConnectionState.STATE_CONNECTED.value})).start()
                initData['controller'].devices[event.data['mac']]['Connected'] = True
            elif patterns['deviceDisconnected'].search(event.data['data']):
                triggerEvent(CallBackEvents.FROFILE_CONNECTION_STATE_CHANGED.value, json.dumps({
                    'mac': event.data['mac'],
                    'state': ConnectionState.STATE_DISCONNECTED.value
                    
                }))
                if event.data['mac'] in initData['controller'].devices:
                    initData['controller'].devices[event.data['mac']]['Connected'] = False
                else:
                    logging.debug(f"{event.data['mac']} disconnected but not in devices!!")
            elif patterns['deviceAliased'].search(event.data['data']):          
                triggerEvent(CallBackEvents.DEVICE_PROPERTY_CHANGED.value, json.dumps({
                    'mac': event.data['mac'],
                    BluetoothProperty.BT_PROPERTY_REMOTE_FRIENDLY_NAME.value: event.data['data'].split(':', 1)[1].strip()
                }))

    def onAgent(event: BluetoothEvent):
        if event.data['subType'] is CallBackEvents.PIN_REQUEST:
            triggerEvent(CallBackEvents.PIN_REQUEST.value, json.dumps({
               'mac': event.data['mac'],
               'name': event.data['name'],
               'pin': event.data['pin']
            }))

    def init() -> bool:
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

    def startMonitoring() -> bool:
        return initData['controller'].startMonitoring()

    def serviceThread():
        global initData
        while not initData['stopping']:
            if not initData['controller']:
                initData['controller'] = BluetoothController()
                initData['controller'].onDeviceDiscovered(onDeviceDiscovered)
                initData['controller'].onDeviceRemoved(onDeviceRemoved)
                initData['controller'].onChg(onChg)
                initData['controller'].onAgent(onAgent)
            IBluetooth.addService(args, registerCallback, unregisterCallback,init,
                cleanup, enable, disable, getAdapterProperties, getAdapterProperty,
                setAdapterProperty, createBond, removeBond, cancelBond, pairingIsBusy,
                getConnectionState, startDiscovery, cancelDiscovery, connect, disconnect,
                setDeviceProperty, startMonitoring)

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
