# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading
import time
from enum import Enum, IntEnum
from typing import Callable, Dict, Optional

from gi.repository import Gio, GLib

BLUEZ = "org.bluez"
OM_IF = "org.freedesktop.DBus.ObjectManager"
PROPS_IF = "org.freedesktop.DBus.Properties"
ADAPTER_IF = "org.bluez.Adapter1"
DEVICE_IF = "org.bluez.Device1"
AGENT_IF = "org.bluez.Agent1"
AGENT_MGR_IF = "org.bluez.AgentManager1"
AGENT_MGR_PATH = "/org/bluez"
AGENT_PATH = "/openfde/agent"

class Event(IntEnum):
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
    SSP_REQUEST = 10

class Prop(IntEnum):
    BDNAME = 0x01
    BDADDR = 0x02
    UUIDS = 0x03
    CLASS_OF_DEVICE = 0x04
    TYPE_OF_DEVICE = 0x05
    ADAPTER_SCAN_MODE = 0x07
    ADAPTER_BONDED_DEVICES = 0x08
    ADAPTER_DISCOVERABLE_TIMEOUT = 0x09
    REMOTE_FRIENDLY_NAME = 0x0A
    REMOTE_RSSI = 0x0B
    LOCAL_IO_CAPS = 0x0E
    DYNAMIC_AUDIO_BUFFER = 0x10

BOND_NONE, BOND_BONDING, BOND_BONDED = 0, 1, 2
STATE_DISCONNECTED, STATE_CONNECTING, STATE_CONNECTED, STATE_DISCONNECTING = 0, 1, 2, 3
SCAN_MODE_NONE, SCAN_MODE_CONNECTABLE, SCAN_MODE_CONNECTABLE_DISCOVERABLE = 0, 1, 2
(VARIANT_PASSKEY_CONFIRMATION, VARIANT_PASSKEY_ENTRY, VARIANT_CONSENT,
 VARIANT_PASSKEY_NOTIFICATION, VARIANT_PARTICIPATION) = 0, 1, 2, 3, 4


def normalizeMac(mac: str) -> str:
    return (mac or "").strip().upper().replace("-", ":")

def macToPath(adapterPath: str, mac: str) -> str:
    return "%s/dev_%s" % (adapterPath, normalizeMac(mac).replace(":", "_"))

def pathToMac(path: str) -> str:
    name = (path or "").rsplit("/", 1)[-1]
    if name.startswith("dev_"):
        return name[4:].replace("_", ":")
    return name

def classString(cls) -> str:
    try:
        if isinstance(cls, str):
            return "0x%08X" % (int(cls, 16) & 0xFFFFFFFF)
        return "0x%08X" % (int(cls) & 0xFFFFFFFF)
    except (TypeError, ValueError):
        return "0x00000000"

def uuidsHex(uuids) -> str:
    out = []
    for u in (uuids or []):
        out.append(str(u).replace("-", "").upper())
    return "".join(out)

def isMacLikeName(name) -> bool:
    if not name:
        return False
    s = str(name).strip().upper()
    if not s:
        return False
    for prefix in ("LE-", "LE_", "LE "):
        if s.startswith(prefix):
            s = s[3:].strip()
            break
    for sep in ("-", "_", " ", "."):
        s = s.replace(sep, ":")
    parts = s.split(":")
    if len(parts) == 6 and all(len(p) == 2 and all(c in "0123456789ABCDEF" for c in p)
                               for p in parts):
        return True
    if len(s) == 12 and all(c in "0123456789ABCDEF" for c in s):
        return True
    return False

class BluezBackend:
    AGENT_XML = """
    <node>
      <interface name="org.bluez.Agent1">
        <method name="Release"/>
        <method name="Cancel"/>
        <method name="RequestPinCode">
          <arg type="o" name="device" direction="in"/><arg type="s" name="pincode" direction="out"/>
        </method>
        <method name="DisplayPinCode">
          <arg type="o" name="device" direction="in"/><arg type="s" name="pincode" direction="in"/>
        </method>
        <method name="RequestPasskey">
          <arg type="o" name="device" direction="in"/><arg type="u" name="passkey" direction="out"/>
        </method>
        <method name="DisplayPasskey">
          <arg type="o" name="device" direction="in"/><arg type="u" name="passkey" direction="in"/>
          <arg type="q" name="entered" direction="in"/>
        </method>
        <method name="RequestConfirmation">
          <arg type="o" name="device" direction="in"/><arg type="u" name="passkey" direction="in"/>
        </method>
        <method name="RequestAuthorization">
          <arg type="o" name="device" direction="in"/>
        </method>
        <method name="AuthorizeService">
          <arg type="o" name="device" direction="in"/><arg type="s" name="uuid" direction="in"/>
        </method>
      </interface>
    </node>
    """

    def __init__(self, onEvent: Optional[Callable] = None,
                 agentCapability: str = "KeyboardDisplay",
                 pairTimeout: int = 45,
                 connectTimeout: int = 30):
        self._onEvent = onEvent
        self.agentCapability = agentCapability
        self.pairTimeout = pairTimeout
        self.connectTimeout = connectTimeout

        self.devices: Dict[str, Dict] = {}
        self.controller: Dict = {
            'Alias': 'OpenFDE',
            'Name': 'OpenFDE',
            'Mac': '11:22:33:44:55:66',
            'Class': '0x00000000',
            'UUIDs': '',
            'Powered': False,
            'Discoverable': False,
            'Pairable': False,
            'Discovering': False,
            'DiscoverableTimeout': 0
        }
        self.adapterPath: Optional[str] = None

        self._pairing = set()
        self._watchdogs: Dict[str, int] = {}
        self._lastBond: Dict[str, int] = {}
        self._lastConn: Dict[str, int] = {}
        self._pendingAgent: Dict[str, tuple] = {}
        self._initError: Optional[Exception] = None
        self._agentRegId = None

        self._ctx = GLib.MainContext.new()
        self._loop = GLib.MainLoop.new(self._ctx, False)
        self._ready = threading.Event()
        self._stopping = False
        self._bus = None

        self._thread = threading.Thread(target=self._threadMain, name="bluez-dbus", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            logging.error("BluezBackend: D-Bus thread init timeout")

    def _threadMain(self):
        self._ctx.push_thread_default()
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            if self._bus is None:
                raise RuntimeError("connect system bus fail")
            self._attachSignals()
            self._snapshot()
            if self.agentCapability and self.agentCapability != "off":
                try:
                    self._registerAgent(self.agentCapability)
                except Exception as e:
                    logging.error("BluezBackend: register agent fail: %s" % e)
        except Exception as e:
            self._initError = e
            logging.error("BluezBackend: init fail: %s" % e)
        finally:
            self._ready.set()
        self._loop.run()

    def _schedule(self, fn, *args, **kwargs):
        def _run():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logging.error("BluezBackend: _schedule %s fail: %s"
                              % (getattr(fn, "__name__", fn), e))
            return False
        self._ctx.invoke_full(GLib.PRIORITY_DEFAULT, _run)

    def _invokeSync(self, fn, *args, timeout=4.0):
        if threading.current_thread() is self._thread:
            return fn(*args)
        done = threading.Event()
        box = {}

        def _run():
            try:
                box['value'] = fn(*args)
            except Exception as e:
                box['error'] = e
            finally:
                done.set()
            return False

        self._ctx.invoke_full(GLib.PRIORITY_DEFAULT, _run)
        if not done.wait(timeout):
            raise RuntimeError("BluezBackend: backend thread not response")
        if 'error' in box:
            raise box['error']
        return box.get('value')

    def _emit(self, what, data=None):
        if not self._onEvent:
            return
        try:
            w = int(what)
            self._onEvent(w, data)
        except Exception as e:
            logging.error("BluezBackend: event callback fail (%s): %s" % (what, e))

    def _emitLater(self, delayMs, what, data=None):
        def _fire():
            if what == Event.FROFILE_CONNECTION_STATE_CHANGED:
                self._emitConn(data.get('mac'), data.get('state'))
            elif what == Event.BOND_STATE_CHANGE:
                self._emitBond(data.get('mac'), data.get('state'))
            else:
                self._emit(what, data)
            return False
        GLib.timeout_add(int(delayMs), _fire)

    def _unwrap(self, res):
        val = res.unpack()
        if isinstance(val, tuple) and len(val) == 1:
            return val[0]
        return val

    def _call(self, path, iface, method, params=None, timeout=15000):
        try:
            return self._bus.call_sync(BLUEZ, path, iface, method, params, None,
                                       Gio.DBusCallFlags.NONE, timeout, None)
        except GLib.Error as e:
            raise RuntimeError("%s.%s fail: %s" % (iface, method, e.message))

    def _callAsync(self, path, iface, method, params, timeoutMs, onDone):
        def _finish(conn, res):
            try:
                conn.call_finish(res)
                onDone(None)
            except GLib.Error as e:
                onDone(RuntimeError("%s.%s fail: %s" % (iface, method, e.message)))
        self._bus.call(BLUEZ, path, iface, method, params, None,
                       Gio.DBusCallFlags.NONE, timeoutMs, None, _finish)

    def _getAll(self, path, iface):
        return self._unwrap(self._call(path, PROPS_IF, "GetAll", GLib.Variant("(s)", (iface,)), 8000))

    def _set(self, path, iface, name, variant, timeout=15000):
        self._call(path, PROPS_IF, "Set", GLib.Variant("(ssv)", (iface, name, variant)), timeout)

    def _managedObjects(self):
        return self._unwrap(self._call("/", OM_IF, "GetManagedObjects", None, 10000))

    def _snapshot(self):
        objects = self._managedObjects()
        adapterPath = None
        adapterProps = None
        for path, ifaces in objects.items():
            if ADAPTER_IF in ifaces:
                adapterPath = path
                adapterProps = ifaces[ADAPTER_IF]
                break
        if adapterPath is None:
            self.controller['Powered'] = False
            logging.warning("BluezBackend: no org.bluez adapter found on system bus (bluetoothd running?)")
            return
        self.adapterPath = adapterPath
        self._updateAdapter(adapterProps)
        self.devices = {}
        for path, ifaces in objects.items():
            if path.startswith(self.adapterPath + "/dev_") and DEVICE_IF in ifaces:
                props = ifaces[DEVICE_IF]
                name = props.get("Name")
                if name and not isMacLikeName(name):
                    mac = normalizeMac(props.get("Address") or pathToMac(path))
                    self.devices[mac] = self._deviceEntry(mac, props)

    def _updateAdapter(self, props):
        c = self.controller
        if "Address" in props:
            c['Mac'] = props["Address"]
        if "Alias" in props:
            c['Alias'] = props["Alias"]
        if "Name" in props:
            c['Name'] = props["Name"]
        if "Class" in props:
            c['Class'] = classString(props["Class"])
        if "UUIDs" in props:
            c['UUIDs'] = uuidsHex(props["UUIDs"])
        for key in ("Powered", "Discoverable", "Pairable", "Discovering"):
            if key in props:
                c[key] = bool(props[key])
        if "DiscoverableTimeout" in props:
            c['DiscoverableTimeout'] = props["DiscoverableTimeout"]

    def _deviceEntry(self, mac, props):
        old = self.devices.get(mac, {})
        paired = bool(props.get("Paired", old.get('Paired', False)))
        entry = {
            'Mac': mac,
            'Name': props.get("Alias") or props.get("Name") or old.get('Name') or mac,
            'Alias': props.get("Alias") or old.get('Alias'),
            'Class': classString(props["Class"]) if "Class" in props else old.get('Class', '0x00000000'),
            'UUIDs': uuidsHex(props["UUIDs"]) if "UUIDs" in props else old.get('UUIDs', ''),
            'Paired': paired,
            'Trusted': bool(props.get("Trusted", old.get('Trusted', False))),
            'Connected': paired and bool(props.get("Connected", old.get('Connected', False))),
            'ServicesResolved': bool(props.get("ServicesResolved", old.get('ServicesResolved', False))),
        }
        entry['_raw'] = dict(props)
        return entry

    def _devicePath(self, mac):
        mac = normalizeMac(mac)
        for p, props in self._rawDevicePaths().items():
            if normalizeMac(props.get("Address", "")) == mac:
                return p
        return macToPath(self.adapterPath or "", mac)

    def _rawDevicePaths(self):
        try:
            objects = self._managedObjects()
        except Exception:
            return {}
        return {p: i[DEVICE_IF] for p, i in objects.items()
                if p.startswith((self.adapterPath or "") + "/dev_") and DEVICE_IF in i}

    def _attachSignals(self):
        self._bus.signal_subscribe(BLUEZ, OM_IF, "InterfacesAdded", None, None,
                                   Gio.DBusSignalFlags.NONE, self._onInterfacesAdded)
        self._bus.signal_subscribe(BLUEZ, OM_IF, "InterfacesRemoved", None, None,
                                   Gio.DBusSignalFlags.NONE, self._onInterfacesRemoved)
        self._bus.signal_subscribe(BLUEZ, PROPS_IF, "PropertiesChanged", None, None,
                                   Gio.DBusSignalFlags.NONE, self._onPropertiesChanged)
        self._bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus",
                                   "NameOwnerChanged", None, BLUEZ,
                                   Gio.DBusSignalFlags.NONE, self._onNameOwnerChanged)

    def _onNameOwnerChanged(self, conn, sender, path, iface, signal, params):
        name, old, new = params.unpack()
        if new:
            logging.warning("BluezBackend: bluetoothd reappeared, re-snapshot and re-register agent")
        else:
            logging.warning("BluezBackend: bluetoothd disappeared (service restart/exit)")
        try:
            self._snapshot()
            if new and self.agentCapability and self.agentCapability != "off":
                self._registerAgent(self.agentCapability)
        except Exception as e:
            logging.error("BluezBackend: recovery failed: %s" % e)

    def _fromOurAdapter(self, path):
        return bool(self.adapterPath) and path.startswith(self.adapterPath + "/dev_")

    def _onInterfacesAdded(self, conn, sender, path, iface, signal, params):
        objPath, ifaces = params.unpack()
        if ADAPTER_IF in ifaces and not self.adapterPath:
            self.adapterPath = objPath
            self._updateAdapter(ifaces[ADAPTER_IF])
        elif DEVICE_IF in ifaces and self._fromOurAdapter(objPath):
            props = ifaces[DEVICE_IF]
            name = props.get("Name")
            if not name or isMacLikeName(name):
                return
            mac = normalizeMac(props.get("Address") or pathToMac(objPath))
            self.devices[mac] = self._deviceEntry(mac, props)
            self._emit(Event.DEVICE_PROPERTY_CHANGED, self._devicePayload(mac, props))
            self._emit(Event.DEVICE_FOUND, {'mac': mac})
            if props.get("Paired"):
                self._emitBond(mac, BOND_BONDED)
            if props.get("Paired") and props.get("Connected"):
                self._emitConn(mac, STATE_CONNECTED)

    def _onInterfacesRemoved(self, conn, sender, path, iface, signal, params):
        objPath, names = params.unpack()
        if DEVICE_IF not in names or not self._fromOurAdapter(objPath):
            return
        mac = normalizeMac(pathToMac(objPath))
        entry = self.devices.pop(mac, None) or {}
        if entry:
            if self._lastConn.get(mac, STATE_DISCONNECTED) != STATE_DISCONNECTED:
                self._emitConn(mac, STATE_DISCONNECTED)
            if self._lastBond.get(mac, BOND_NONE) != BOND_NONE:
                self._emitBond(mac, BOND_NONE)
            self._lastBond.pop(mac, None)
            self._lastConn.pop(mac, None)

    def _onPropertiesChanged(self, conn, sender, path, iface, signal, params):
        ifaceName, changed, invalidated = params.unpack()
        keys = set(changed)
        if (ifaceName not in (ADAPTER_IF, DEVICE_IF)
            or not changed
            or keys == {"RSSI"}
            or keys == {"ManufacturerData"}):
            return
        if ifaceName == ADAPTER_IF:
            self._updateAdapter(changed)
            if "Powered" in changed:
                self._emit(Event.BT_STATE_ON if changed["Powered"] else Event.BT_STATE_OFF)
                if changed["Powered"]:
                    self.triggerPairedAndConnectedDevices()
            if "Discovering" in changed:
                self._emit(Event.BT_DISCOVERY_STARTED if changed["Discovering"]
                           else Event.BT_DISCOVERY_STOPPED)
            payload = self._adapterPayload(changed)
            if payload:
                self._emit(Event.ADAPTER_PROPERTY_CHANGED, payload)
        elif ifaceName == DEVICE_IF and self._fromOurAdapter(path):
            mac = normalizeMac(pathToMac(path))
            entry = self.devices.get(mac)
            if entry:
                rawProps = dict(entry.get('_raw') or {})
                rawProps.update(changed)
                self.devices[mac] = self._deviceEntry(mac, rawProps)
                if "Paired" in changed:
                    self._emitBond(mac, BOND_BONDED if changed["Paired"] else BOND_NONE)
                if "Connected" in changed and rawProps.get("Paired"):
                    self._emitConn(mac, STATE_CONNECTED if changed["Connected"] else STATE_DISCONNECTED)
                payload = self._devicePayload(mac, changed)
                if len(payload) > 2:
                    self._emit(Event.DEVICE_PROPERTY_CHANGED, payload)

    def _emitBond(self, mac, state):
        if self._lastBond.get(mac) == state:
            return
        self._emit(Event.BOND_STATE_CHANGE, {'mac': mac, 'state': int(state)})
        self._lastBond[mac] = state

    def _emitConn(self, mac, state):
        if self._lastConn.get(mac) == state:
            return
        self._emit(Event.FROFILE_CONNECTION_STATE_CHANGED, {'mac': mac, 'state': int(state)})
        self._lastConn[mac] = state

    def _adapterPayload(self, props):
        data = {}
        if "Alias" in props:
            data[str(Prop.BDNAME.value)] = props["Alias"]
        if "Address" in props:
            data[str(Prop.BDADDR.value)] = props["Address"]
        if "Class" in props:
            data[str(Prop.CLASS_OF_DEVICE.value)] = classString(props["Class"])
        if "UUIDs" in props:
            data[str(Prop.UUIDS.value)] = uuidsHex(props["UUIDs"])
        return data

    def _scanModePayload(self):
        mode = SCAN_MODE_NONE
        if self.controller.get('Discoverable') and self.controller.get('Pairable'):
            mode = SCAN_MODE_CONNECTABLE_DISCOVERABLE
        elif self.controller.get('Pairable'):
            mode = SCAN_MODE_CONNECTABLE
        return {str(Prop.ADAPTER_SCAN_MODE.value): str(mode)}

    def _devicePayload(self, mac, props):
        data = {'mac': mac, str(Prop.BDADDR.value): mac}
        if "Class" in props:
            data[str(Prop.CLASS_OF_DEVICE.value)] = classString(props["Class"])
        name = props.get("Alias") or props.get("Name")
        if name:
            data[str(Prop.BDNAME.value)] = name
            data[str(Prop.REMOTE_FRIENDLY_NAME.value)] = name
        if "UUIDs" in props:
            data[str(Prop.UUIDS.value)] = uuidsHex(props["UUIDs"])
        return data

    def _deviceName(self, mac):
        entry = self.devices.get(normalizeMac(mac)) or {}
        return entry.get('Name') or entry.get('Alias') or normalizeMac(mac)

    def _registerAgent(self, capability="KeyboardDisplay"):
        info = Gio.DBusNodeInfo.new_for_xml(self.AGENT_XML)
        if self._agentRegId is not None:
            self._unregisterAgent()
        self._agentRegId = self._bus.register_object(
            AGENT_PATH, info.interfaces[0], self._onAgentCall, None, None)
        try:
            self._call(AGENT_MGR_PATH, AGENT_MGR_IF, "RegisterAgent",
                       GLib.Variant("(os)", (AGENT_PATH, capability)))
        except Exception as e:
            try:
                self._bus.unregister_object(self._agentRegId)
            except Exception:
                pass
            self._agentRegId = None
            raise RuntimeError("RegisterAgent failed(%s), check bluetoothd running and AgentManager1 at %s"
                               % (e, AGENT_MGR_PATH))
        try:
            self._call(AGENT_MGR_PATH, AGENT_MGR_IF, "RequestDefaultAgent",
                       GLib.Variant("(o)", (AGENT_PATH,)))
        except Exception as e:
            logging.warning("BluezBackend: RequestDefaultAgent failed (non-fatal): %s" % e)
        self.agentCapability = capability

    def _unregisterAgent(self):
        if self._agentRegId is None:
            return
        try:
            self._call(AGENT_MGR_PATH, AGENT_MGR_IF, "UnregisterAgent",
                       GLib.Variant("(o)", (AGENT_PATH,)))
        except Exception:
            pass
        try:
            self._bus.unregister_object(self._agentRegId)
        except Exception:
            pass
        self._agentRegId = None

    def _answerAgent(self, invocation, accept, outVariant=None):
        if accept:
            invocation.return_value(outVariant)
        else:
            try:
                invocation.return_dbus_error("org.bluez.Error.Rejected", "rejected")
            except Exception:
                invocation.return_value(None)

    def _onAgentCall(self, conn, sender, path, iface, method, params, invocation):
        args = params.unpack() if params is not None else ()
        dev = args[0] if args else None
        mac = normalizeMac(pathToMac(dev)) if dev else "?"
        logging.verbose("BluezBackend: agent.%s(%s)" % (method, ", ".join(str(a) for a in args[1:])))
        if method == "RequestConfirmation":
            passkey = int(args[1]) if len(args) > 1 else 0
            self._emit(Event.SSP_REQUEST, {'mac': mac, 'variant': VARIANT_CONSENT})
            pending = self._pendingAgent.pop(mac, None)
            if pending:
                pendedInvocation, kind, _ = pending
                try:
                    pendedInvocation.return_dbus_error("org.bluez.Error.Rejected", "rejected")
                except Exception:
                    pendedInvocation.return_value(None)
            self._pendingAgent[mac] = (invocation, "confirmation", passkey)
        elif method == "DisplayPasskey":
            passkey = int(args[1]) if len(args) > 1 else 0
            self._emit(Event.PIN_REQUEST,
                       {'mac': mac, 'name': self._deviceName(mac), 'pin': passkey})
            invocation.return_value(None)
        elif method in ("RequestAuthorization", "AuthorizeService"):
            self._answerAgent(invocation, True, None)
        elif method in ("Release", "Cancel"):
            pending = self._pendingAgent.pop(mac, None)
            if pending:
                try:
                    pending[0].return_dbus_error("org.bluez.Error.Canceled", "canceled")
                except Exception:
                    pass
            invocation.return_value(None)
        elif method == "DisplayPinCode":
            pin = str(args[1]) if len(args) > 1 else ""
            try:
                pinInt = int(pin)
            except (TypeError, ValueError):
                logging.warning("BluezBackend: DisplayPinCode %s unsupported pin=%r" % (mac, pin))
                pinInt = None
            if pinInt is not None:
                self._emit(Event.PIN_REQUEST,
                           {'mac': mac, 'name': self._deviceName(mac), 'pin': pinInt})
            invocation.return_value(None)
        elif method == "RequestPasskey":
            self._emit(Event.SSP_REQUEST, {'mac': mac,
                       'name': self._deviceName(mac), 'variant': VARIANT_PASSKEY_ENTRY})
            self._pendingAgent[mac] = (invocation, "passkey", None)
        elif method == "RequestPinCode":
            self._emit(Event.PIN_REQUEST, {'mac': mac, 'name': self._deviceName(mac)})
            self._pendingAgent[mac] = (invocation, "pincode", None)
        else:
            invocation.return_value(None)

    def _sspReply(self, mac: str, type: int, accept: bool, passkey: int) -> bool:
        pending = self._pendingAgent.pop(normalizeMac(mac), None)
        if not pending:
            return False
        invocation, kind, _ = pending
        if kind == "confirmation":
            self._answerAgent(invocation, True if accept else False)
        return True

    def sspReply(self, mac: str, type: int, accept: bool, passkey: int) -> bool:
        try:
            return bool(self._invokeSync(self._sspReply, mac, type, accept, passkey,
                                         timeout=4.0))
        except Exception as e:
            logging.error("BluezBackend: sspReply failed: %s" % e)
            return False

    def _pinReply(self, mac: str, accept: bool, pin: str) -> bool:
        pending = self._pendingAgent.pop(normalizeMac(mac), None)
        if not pending:
            return False
        invocation, kind, _ = pending
        if kind == "passkey":
            invocation.return_value(GLib.Variant("(u)", (int(pin or 0),)))
        elif kind == "pincode":
            invocation.return_value(GLib.Variant("(s)", (str(pin or "0000"),)))
        return True

    def pinReply(self, mac: str, accept: bool, pin: str) -> bool:
        try:
            return bool(self._invokeSync(self._pinReply, mac, accept, pin, timeout=4.0))
        except Exception as e:
            logging.error("BluezBackend: pinReply failed: %s" % e)
            return False

    def isEnabled(self) -> bool:
        self._ready.wait(timeout=3)
        return bool(self.controller.get('Powered'))

    def pairingIsBusy(self) -> bool:
        return len(self._pairing) > 0

    def getConnectionState(self, address: str) -> int:
        entry = self.devices.get(normalizeMac(address))
        if entry is None:
            return STATE_DISCONNECTED
        return STATE_CONNECTED if entry.get('Connected') else STATE_DISCONNECTED

    def getAdapterProperties(self) -> bool:
        self._schedule(self._refreshAdapterProps)
        return True

    def _refreshAdapterProps(self):
        if not self.adapterPath:
            try:
                self._snapshot()
            except Exception as e:
                logging.error("BluezBackend: snapshot failed: %s" % e)
            return
        self._updateAdapter(self._getAll(self.adapterPath, ADAPTER_IF))

    def powerOn(self) -> bool:
        self._schedule(self._setPowered, True)
        return True

    def powerOff(self) -> bool:
        self._schedule(self._setPowered, False)
        return True

    def _setPowered(self, on):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            self._refreshAdapterProps()
        if not self.adapterPath:
            logging.error("BluezBackend: no adapter, cannot power %s" % on)
            self._emit(Event.BT_STATE_ON if on else Event.BT_STATE_OFF)
            return
        before = bool(self.controller.get('Powered'))
        self._set(self.adapterPath, ADAPTER_IF, "Powered", GLib.Variant("b", bool(on)), 30000)
        if before == bool(on):
            if on:
                self._emit(Event.BT_STATE_ON)
                self.triggerPairedAndConnectedDevices()
            else:
                self.devices = {}
                self._emit(Event.BT_STATE_OFF)
        self._schedule(self._refreshAdapterProps)

    def startDiscovery(self) -> bool:
        self._schedule(self._startDiscovery)
        return True

    def _startDiscovery(self):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            self._refreshAdapterProps()
        if not self.adapterPath:
            return
        try:
            self._call(self.adapterPath, ADAPTER_IF, "StartDiscovery", None, 15000)
        except RuntimeError as e:
            logging.verbose("BluezBackend: StartDiscovery: %s" % e)
            self._emit(Event.BT_DISCOVERY_STARTED)
        self._snapshot()
        self._replayKnownDevices()

    def cancelDiscovery(self) -> bool:
        self._schedule(self._stopDiscovery)
        return True

    def _stopDiscovery(self):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            return
        try:
            self._call(self.adapterPath, ADAPTER_IF, "StopDiscovery", None, 15000)
        except RuntimeError as e:
            logging.verbose("BluezBackend: StopDiscovery: %s" % e)
            self._emit(Event.BT_DISCOVERY_STOPPED)

    def _replayKnownDevices(self):
        offset = 0
        for mac, entry in list(self.devices.items()):
            self._emitLater(offset, Event.DEVICE_PROPERTY_CHANGED, self._entryPayload(entry))
            self._emitLater(offset + 50, Event.DEVICE_FOUND, {'mac': mac})
            offset += 100

    def _entryPayload(self, entry):
        mac = entry.get('Mac')
        props = {'mac': mac, str(Prop.BDADDR.value): mac}
        if entry.get('Class'):
            props[str(Prop.CLASS_OF_DEVICE.value)] = entry['Class']
        if entry.get('Name'):
            props[str(Prop.BDNAME.value)] = entry['Name']
            props[str(Prop.REMOTE_FRIENDLY_NAME.value)] = entry['Name']
        if entry.get('UUIDs'):
            props[str(Prop.UUIDS.value)] = entry['UUIDs']
        return props

    def triggerPairedAndConnectedDevices(self):
        paired = [e for e in self.devices.values() if e.get('Paired')]
        offset = 0
        for entry in paired:
            mac = entry.get('Mac')
            self._emitLater(offset, Event.DEVICE_PROPERTY_CHANGED, self._entryPayload(entry))
            self._lastBond.pop(mac, None)
            self._emitLater(offset + 100, Event.BOND_STATE_CHANGE,
                            {'mac': mac, 'state': BOND_BONDING})
            self._emitLater(offset + 200, Event.BOND_STATE_CHANGE,
                            {'mac': mac, 'state': BOND_BONDED})
            if entry.get('Connected'):
                self._lastConn.pop(mac, None)
                self._emitLater(offset + 300, Event.FROFILE_CONNECTION_STATE_CHANGED,
                                {'mac': mac, 'state': STATE_CONNECTED})
            offset += 400

    def createBond(self, address: str, addressType: int = 0, transport: int = 0) -> bool:
        mac = normalizeMac(address)
        self._schedule(self._pair, mac)
        return True

    def _pair(self, mac):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            self._refreshAdapterProps()
        path = self._devicePath(mac)
        self._pairing.add(mac)
        self._lastBond.pop(mac, None)
        self._emitBond(mac, BOND_BONDING)

        def _done(err):
            self._cancelWatchdog("pair:" + mac)
            self._pairing.discard(mac)
            if err:
                logging.error("BluezBackend: %s pairing failed: %s" % (mac, err))
                self._emitBond(mac, BOND_NONE)
                return
            props = {}
            try:
                props = self._getAll(path, DEVICE_IF)
            except Exception as e:
                logging.warning("BluezBackend: read properties after pairing failed: %s" % e)
            if props.get("Paired"):
                self.devices[mac] = self._deviceEntry(mac, props)
                if "UUIDs" in props:
                    self._emit(Event.DEVICE_PROPERTY_CHANGED,
                               {'mac': mac, str(Prop.UUIDS.value): uuidsHex(props["UUIDs"])})
                self._emitBond(mac, BOND_BONDED)
            else:
                logging.error("BluezBackend: %s Pair() returned but not Paired" % mac)
                self._emitBond(mac, BOND_NONE)

        def _timeout():
            self._watchdogs.pop("pair:" + mac, None)
            if mac in self._pairing:
                logging.error("BluezBackend: %s pairing timeout, CancelPairing" % mac)
                try:
                    self._call(path, DEVICE_IF, "CancelPairing", None, 5000)
                except Exception as e:
                    logging.warning("BluezBackend: CancelPairing: %s" % e)
                self._pairing.discard(mac)
                self._emitBond(mac, BOND_NONE)
            return False

        self._watchdogs["pair:" + mac] = GLib.timeout_add_seconds(self.pairTimeout, _timeout)
        self._callAsync(path, DEVICE_IF, "Pair", None, self.pairTimeout * 1000, _done)

    def removeBond(self, address: str) -> bool:
        mac = normalizeMac(address)
        self._schedule(self._removeBond, mac)
        return True

    def _removeBond(self, mac):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            self._refreshAdapterProps()
        if not self.adapterPath:
            return
        path = self._devicePath(mac)
        try:
            self._call(self.adapterPath, ADAPTER_IF, "RemoveDevice",
                       GLib.Variant("(o)", (path,)), 15000)
        except RuntimeError as e:
            logging.error("BluezBackend: RemoveDevice %s failed: %s" % (mac, e))
        self.devices.pop(mac, None)
        self._emitBond(mac, BOND_NONE)

    def cancelBond(self, address: str) -> bool:
        mac = normalizeMac(address)
        self._schedule(self._cancelBond, mac)
        return True

    def _cancelBond(self, mac):
        if mac in self._pairing:
            path = self._devicePath(mac)
            try:
                self._call(path, DEVICE_IF, "CancelPairing", None, 5000)
            except Exception as e:
                logging.warning("BluezBackend: CancelPairing: %s" % e)
            self._pairing.discard(mac)
            self._cancelWatchdog("pair:" + mac)
            self._emitBond(mac, BOND_NONE)
            return
        self._removeBond(mac)

    def _cancelWatchdog(self, key):
        sid = self._watchdogs.pop(key, None)
        if sid is not None:
            try:
                GLib.source_remove(sid)
            except Exception:
                pass

    def connect(self, address: str) -> bool:
        mac = normalizeMac(address)
        self._schedule(self._connect, mac)
        return True

    def _connect(self, mac):
        self._ready.wait(timeout=5)
        entry = self.devices.get(mac) or {}
        self._lastConn.pop(mac, None)
        if entry.get('Connected'):
            self._emitConn(mac, STATE_CONNECTED)
            return
        path = self._devicePath(mac)
        self._emitConn(mac, STATE_CONNECTING)

        def _done(err):
            self._cancelWatchdog("conn:" + mac)
            if err:
                logging.error("BluezBackend: connect %s failed: %s" % (mac, err))
                self._emitConn(mac, STATE_DISCONNECTED)
                return
            props = {}
            try:
                props = self._getAll(path, DEVICE_IF)
            except Exception:
                pass
            if props:
                self.devices[mac] = self._deviceEntry(mac, props)
            if props.get("Connected"):
                self._emitConn(mac, STATE_CONNECTED)
            else:
                logging.verbose("BluezBackend: %s Connect() returned but Connected=false" % mac)
                self._emitConn(mac, STATE_DISCONNECTED)

        def _timeout():
            self._watchdogs.pop("conn:" + mac, None)
            logging.warning("BluezBackend: %s connect timeout" % mac)
            self._emitConn(mac, STATE_DISCONNECTED)
            return False

        self._watchdogs["conn:" + mac] = GLib.timeout_add_seconds(self.connectTimeout, _timeout)
        self._callAsync(path, DEVICE_IF, "Connect", None, self.connectTimeout * 1000, _done)

    def disconnect(self, address: str) -> bool:
        mac = normalizeMac(address)
        self._schedule(self._disconnect, mac)
        return True

    def _disconnect(self, mac):
        self._ready.wait(timeout=5)
        entry = self.devices.get(mac) or {}
        path = self._devicePath(mac)
        self._lastConn.pop(mac, None)
        if not entry.get('Connected'):
            self._emitConn(mac, STATE_DISCONNECTED)
            return
        self._emitConn(mac, STATE_DISCONNECTING)

        def _done(err):
            if err:
                logging.error("BluezBackend: disconnect %s failed: %s" % (mac, err))
            props = {}
            try:
                props = self._getAll(path, DEVICE_IF)
            except Exception:
                pass
            if props:
                self.devices[mac] = self._deviceEntry(mac, props)
            self._emitConn(mac, STATE_CONNECTED if props.get("Connected") else STATE_DISCONNECTED)

        self._callAsync(path, DEVICE_IF, "Disconnect", None, 30000, _done)

    def getAdapterProperty(self, type: int) -> bool:
        t = int(type)
        if t == Prop.BDNAME.value:
            alias = self.controller.get('Alias')
            if alias:
                self._emit(Event.ADAPTER_PROPERTY_CHANGED, {str(Prop.BDNAME.value): alias})
            return True
        if t == Prop.BDADDR.value:
            mac = self.controller.get('Mac')
            if mac:
                self._emit(Event.ADAPTER_PROPERTY_CHANGED, {str(Prop.BDADDR.value): mac})
            return True
        if t == Prop.CLASS_OF_DEVICE.value:
            data = {str(Prop.CLASS_OF_DEVICE.value): self.controller.get('Class', '0x00000000')}
            data.update(self._scanModePayload())
            self._emit(Event.ADAPTER_PROPERTY_CHANGED, data)
            return True
        if t == Prop.UUIDS.value:
            uuids = self.controller.get('UUIDs')
            if uuids:
                self._emit(Event.ADAPTER_PROPERTY_CHANGED, {str(Prop.UUIDS.value): uuids})
            return True
        if t == Prop.ADAPTER_BONDED_DEVICES.value:
            macs = [mac for mac, e in self.devices.items() if e.get('Paired')]
            if not macs:
                return True
            self._emit(Event.ADAPTER_PROPERTY_CHANGED,
                       {str(Prop.ADAPTER_BONDED_DEVICES.value): " ".join(macs)})
            return True
        if t in (Prop.LOCAL_IO_CAPS.value, Prop.DYNAMIC_AUDIO_BUFFER.value):
            return True
        logging.warning("BluezBackend: unhandled getAdapterProperty type=0x%02X" % t)
        return False

    def setAdapterProperty(self, type: int, val: str) -> bool:
        t = int(type)
        if t == Prop.BDNAME.value:
            self._schedule(self._setAdapterAlias, str(val))
            return True
        if t == Prop.ADAPTER_SCAN_MODE.value:
            self._schedule(self._setScanMode, str(val))
            return True
        if t == Prop.ADAPTER_DISCOVERABLE_TIMEOUT.value:
            self._schedule(self._setDiscoverableTimeout, str(val))
            return True
        if t in (Prop.LOCAL_IO_CAPS.value, Prop.DYNAMIC_AUDIO_BUFFER.value):
            return True
        logging.warning("BluezBackend: unhandled setAdapterProperty type=0x%02X" % t)
        return False

    def _setAdapterAlias(self, name):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            self._refreshAdapterProps()
        if not self.adapterPath:
            return
        self._set(self.adapterPath, ADAPTER_IF, "Alias", GLib.Variant("s", name))
        self.controller['Alias'] = name

    def _setScanMode(self, mode):
        self._ready.wait(timeout=5)
        if not self.adapterPath:
            self._refreshAdapterProps()
        if not self.adapterPath:
            return
        try:
            m = int(mode)
        except (TypeError, ValueError):
            logging.error("BluezBackend: mode(%r) error" % mode)
            return
        if m == SCAN_MODE_CONNECTABLE_DISCOVERABLE:
            self._set(self.adapterPath, ADAPTER_IF, "Discoverable", GLib.Variant("b", True))
            self._set(self.adapterPath, ADAPTER_IF, "Pairable", GLib.Variant("b", True))
        elif m == SCAN_MODE_CONNECTABLE:
            self._set(self.adapterPath, ADAPTER_IF, "Pairable", GLib.Variant("b", True))
            self._set(self.adapterPath, ADAPTER_IF, "Discoverable", GLib.Variant("b", False))
        elif m == SCAN_MODE_NONE:
            self._set(self.adapterPath, ADAPTER_IF, "Discoverable", GLib.Variant("b", False))
            self._set(self.adapterPath, ADAPTER_IF, "Pairable", GLib.Variant("b", False))
        else:
            logging.error("BluezBackend: unknown ScanMode %s" % m)
        self._schedule(self._refreshAdapterProps)

    def _setDiscoverableTimeout(self, val):
        self._ready.wait(timeout=5)
        try:
            timeout = int(val)
        except (TypeError, ValueError):
            return
        if timeout <= 0 or not self.adapterPath:
            return

        def _off():
            self._watchdogs.pop("discoverable", None)
            try:
                self._set(self.adapterPath, ADAPTER_IF, "Discoverable", GLib.Variant("b", False))
            except Exception as e:
                logging.verbose("BluezBackend: turn off Discoverable failed: %s" % e)
            return False

        self._cancelWatchdog("discoverable")
        self._watchdogs["discoverable"] = GLib.timeout_add_seconds(timeout, _off)

    def setDeviceProperty(self, address: str, type: int, val: str) -> bool:
        t = int(type)
        if t == Prop.REMOTE_FRIENDLY_NAME.value:
            self._schedule(self._setDeviceAlias, normalizeMac(address), str(val))
            return True
        logging.warning("BluezBackend: unhandled setDeviceProperty type=0x%02X" % t)
        return False

    def _setDeviceAlias(self, mac, name):
        path = self._devicePath(mac)
        self._set(path, DEVICE_IF, "Alias", GLib.Variant("s", name))
        entry = self.devices.get(mac)
        if entry is not None:
            entry['Alias'] = name
            entry['Name'] = name

    def cleanup(self):
        self._stopping = True
        self._ready.wait(timeout=3)
        try:
            self._invokeSync(self._unregisterAgent, timeout=2)
        except Exception:
            pass
        for key in list(self._watchdogs.keys()):
            self._cancelWatchdog(key)
        try:
            self._ctx.invoke_full(GLib.PRIORITY_DEFAULT,
                                  lambda: (self._loop.quit(), False)[1])
        except Exception:
            pass
        logging.debug("BluezBackend: cleanup done")

    def getAdapterName(self):
        self._ready.wait(timeout=3)
        return self.controller.get('Alias')