# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import os
import socket
import struct
import threading
import time
from enum import IntEnum
from typing import Callable, Dict, Optional
from gi.repository import Gio, GLib

NM = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_IF = "org.freedesktop.NetworkManager"
NM_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NM_SETTINGS_IF = "org.freedesktop.NetworkManager.Settings"
PROPS_IF = "org.freedesktop.DBus.Properties"
DEV_IF = "org.freedesktop.NetworkManager.Device"
WIFI_IF = "org.freedesktop.NetworkManager.Device.Wireless"
AP_IF = "org.freedesktop.NetworkManager.AccessPoint"
ACT_IF = "org.freedesktop.NetworkManager.Connection.Active"
SETCON_IF = "org.freedesktop.NetworkManager.Settings.Connection"
IP4_IF = "org.freedesktop.NetworkManager.IP4Config"

NM_DEVICE_TYPE_WIFI = 2
NM_ACT_STATE_ACTIVATED = 2

SECURITY_OPEN = 0
SECURITY_WPA2_PSK = 1
SECURITY_SAE = 2

class Event(IntEnum):
    WIFI_STATE_CHANGED = 0
    SCAN_RESULTS_AVAILABLE = 1
    CONNECTION_CHANGED = 2
    RSSI_CHANGED = 3

def _py(v):
    if isinstance(v, GLib.Variant):
        t = v.get_type_string()
        if t == "v":
            return _py(v.unpack())
        if t == "ay":
            try:
                return bytes(v.unpack()).decode("utf-8", "replace")
            except Exception:
                return v
        if t.startswith("a{"):
            return {item.get_child_value(0).unpack(): _py(item.get_child_value(1))
                    for item in (v.get_child_value(i) for i in range(v.n_children()))}
        if t.startswith("a"):
            return [_py(v.get_child_value(i)) for i in range(v.n_children())]
        return v.unpack()
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v).decode("utf-8", "replace")
    if isinstance(v, list):
        if v and all(isinstance(x, int) and 0 <= x <= 255 for x in v):
            try:
                return bytes(v).decode("utf-8", "replace")
            except Exception:
                return v
        return v
    if isinstance(v, dict):
        return {k: _py(x) for k, x in v.items()}
    return v

def _ssid(aprops):
    s = aprops.get("Ssid")
    if not s:
        return "(hidden/empty)"
    return s if isinstance(s, str) else _py(s)

def _settingsSsid(ws):
    s = ws.get("ssid")
    if s is None:
        return "(hidden)"
    return s if isinstance(s, str) else _py(s)

_KEY_MGMT_PSK = 0x100
_KEY_MGMT_8021X = 0x200
_KEY_MGMT_SAE = 0x400
_KEY_MGMT_OWE = 0x800

def _security(wpaFlags, rsnFlags):
    bits = (wpaFlags or 0) | (rsnFlags or 0)
    if bits == 0:
        return "OPEN"
    if bits & _KEY_MGMT_OWE:
        return "OWE"
    if bits & _KEY_MGMT_SAE and bits & _KEY_MGMT_PSK:
        return "WPA3-WPA2"
    if bits & _KEY_MGMT_SAE:
        return "WPA3-SAE"
    if bits & _KEY_MGMT_PSK:
        return "WPA2-PSK"
    if bits & _KEY_MGMT_8021X:
        return "WPA-Enterprise"
    return "WPA"

FAKE_ON_NO_HW = True

def _hostUniqueTag() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "r") as f:
                uid = (f.read() or "").strip()
        except Exception as e:
            logging.warning("NMWifiBackend: read %s fail: %s" % (path, e))
            continue
        if uid:
            return uid[-4:]
        return ""

def _buildFakeSsid() -> str:
    name = "".join(c for c in (socket.gethostname() or "")
                   if c.isalnum() or c in "-_.").strip("-._")
    if name:
        tag = _hostUniqueTag()
        return ("WiFi-" + name + ("-" + tag if tag else ""))[:32]
    tag = _hostUniqueTag()
    if tag:
        return "WiFi-" + tag
    return "WiFi"

FAKE_SSID = _buildFakeSsid()
FAKE_DEV_MAC = "02:11:22:33:44:55"
FAKE_AP_MAC = "02:AA:BB:CC:DD:EE"
FAKE_FREQ = 2412
FAKE_STRENGTH = 76
FAKE_RSSI_DBM = -47
FAKE_BITRATE = 866.7
FAKE_IFNAME = "fde0"
FAKE_STATE = 70
FAKE_SECURITY = "WPA2-PSK"

FAKE_DHCP_IP = "192.168.1.100"
FAKE_DHCP_NETMASK = "255.255.255.0"
FAKE_DHCP_GW = "192.168.1.1"
FAKE_DHCP_DNS = ["192.168.1.1", "8.8.8.8"]
FAKE_DHCP_LEASE = 86400

RSSI_EMIT_MIN_DELTA = 4
RSSI_EMIT_MIN_INTERVAL = 3.0
AP_LIST_EMIT_DELAY_MS = 1000

def _ip4ToDotted(v):
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray, memoryview)):
        v = list(bytes(v))
    if isinstance(v, int):
        try:
            return socket.inet_ntoa(struct.pack("<I", int(v) & 0xffffffff))
        except Exception:
            return None
    if isinstance(v, list) and v and all(isinstance(x, int) and 0 <= x <= 255 for x in v):
        return ".".join(str(int(x) & 0xff) for x in v)
    if isinstance(v, str):
        return v if v not in ("0.0.0.0", "") else None
    return None

def _prefixToNetmask(prefix):
    try:
        p = int(prefix or 24)
        if not (0 <= p <= 32):
            return "255.255.255.0"
        return socket.inet_ntoa(struct.pack("!I", (0xffffffff << (32 - p)) & 0xffffffff))
    except Exception:
        return "255.255.255.0"

class NMWifiBackend:
    def __init__(self, onEvent: Optional[Callable] = None):
        self._onEvent = onEvent
        self._bus = None
        self._ctx = GLib.MainContext.new()
        self._loop = GLib.MainLoop.new(self._ctx, False)
        self._ready = threading.Event()
        self._stopping = False
        self._initError = None

        self._lock = threading.Lock()
        self._enabled = False
        self._hw = False
        self._device = None
        self._ifname = None
        self._activeAp = None
        self._activeConn = None
        self._fake = False
        self._lastRssi = (None, None, 0.0)
        self._connActive = False
        self._apListGen = 0

        self._thread = threading.Thread(target=self._threadMain, name="nm-wifi-dbus", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            logging.error("NMWifiBackend: D-Bus thread init timeout")

    def _threadMain(self):
        self._ctx.push_thread_default()
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            if self._bus is None:
                raise RuntimeError("connect system bus fail")
            self._attachSignals()
            self._snapshot()
        except Exception as e:
            self._initError = e
            logging.error("NMWifiBackend: init fail: %s" % e)
        finally:
            self._ready.set()
        self._loop.run()

    def _call(self, path, iface, method, params=None, timeout=15000):
        return self._bus.call_sync(NM, path, iface, method, params, None,
                                   Gio.DBusCallFlags.NONE, timeout, None)

    def _getAll(self, path, iface, timeout=8000):
        try:
            res = self._call(path, PROPS_IF, "GetAll", GLib.Variant("(s)", (iface,)), timeout)
            return _py(res.unpack()[0]) or {}
        except Exception as e:
            logging.error("NMWifiBackend: GetAll %s %s fail: %s" % (path, iface, e))
            return {}

    def _set(self, path, iface, prop, variant):
        self._call(path, PROPS_IF, "Set", GLib.Variant("(ssv)", (iface, prop, variant)))

    def _setProp(self, prop, variant):
        self._set(NM_PATH, NM_IF, prop, variant)

    def _wifiDevice(self):
        try:
            devices = _py(self._call(NM_PATH, NM_IF, "GetDevices", None).unpack()[0]) or []
        except Exception as e:
            logging.error("NMWifiBackend: GetDevices fail: %s" % e)
            return None
        wifis = []
        for d in devices:
            dp = self._getAll(d, DEV_IF)
            if dp.get("DeviceType") == NM_DEVICE_TYPE_WIFI:
                wifis.append((d, dp.get("Interface")))
        if not wifis:
            return None
        return wifis[0][0]

    def _snapshot(self):
        root = self._getAll(NM_PATH, NM_IF)
        enabled = bool(root.get("WirelessEnabled"))
        hw = bool(root.get("WirelessHardwareEnabled") or root.get("WirelessEnabled"))
        dev = self._wifiDevice()
        if dev is None:
            hw = False
        fake =  FAKE_ON_NO_HW and dev is None
        if fake:
            enabled = True
            hw = True
        changedEnabled = enabled != self._enabled
        activeConn = None
        activeAp = None
        ifname = None
        if not fake:
            activeConn = self._activeConnection(dev)
            if dev:
                w = self._getAll(dev, WIFI_IF)
                activeAp = w.get("ActiveAccessPoint")
                ifname = w.get("Interface") or self._getAll(dev, DEV_IF).get("Interface")
        with self._lock:
            prevFake = self._fake
            self._fake = fake
            self._enabled = enabled
            self._hw = hw
            self._device = dev
            if fake:
                self._activeConn = {"path": FAKE_AP_MAC, "id": FAKE_SSID,
                                     "state": FAKE_STATE, "conn": None, "ssid": FAKE_SSID}
                self._activeAp = FAKE_AP_MAC
                self._ifname = FAKE_IFNAME
            else:
                self._activeConn = activeConn
                self._activeAp = activeAp
                self._ifname = ifname
            if fake and not prevFake:
                self._connActive = True
            elif prevFake and not fake:
                self._connActive = False
        if fake and not prevFake:
            self._emit(Event.WIFI_STATE_CHANGED, {"enabled": True})
            self._emit(Event.CONNECTION_CHANGED, {"connected": True, "ssid": FAKE_SSID,
                                                  "id": FAKE_SSID})
        if changedEnabled and not (fake and not prevFake):
            self._emit(Event.WIFI_STATE_CHANGED, {"enabled": enabled})

    def _activeConnection(self, dev):
        root = self._getAll(NM_PATH, NM_IF)
        for ac in root.get("ActiveConnections", []):
            ap = self._getAll(ac, ACT_IF)
            if ap.get("Type") != "802-11-wireless":
                continue
            if dev is not None and dev not in ap.get("Devices", []):
                continue
            info = {"path": ac, "id": ap.get("Id"), "state": ap.get("State"), "conn": ap.get("Connection")}
            conn = ap.get("Connection")
            if conn and conn != "/":
                try:
                    settings = _py(self._call(conn, SETCON_IF, "GetSettings", None).unpack()[0]) or {}
                    info["ssid"] = _settingsSsid(settings.get("802-11-wireless") or {})
                except Exception as e:
                    logging.error("NMWifiBackend: GetSettings(conn=%s) fail: %s" % (conn, e))
            return info
        return None

    def _attachSignals(self):
        def onPropertiesChanged(conn, sender, path, iface, signal, params):
            try:
                ifaceName, changed, _invalidated = params.unpack()
            except Exception as e:
                logging.error("NMWifiBackend: props unpack fail (%r): %s" % (params, e))
                return
            changed = changed or {}
            try:
                if (ifaceName == NM_IF
                        and ("WirelessEnabled" in changed or "Devices" in changed)):
                    self._snapshot()
                elif ifaceName == WIFI_IF and path == self._device:
                    if "LastScan" in changed:
                        self._snapshot()
                        self._cancelApListEmit()
                        self._emit(Event.SCAN_RESULTS_AVAILABLE, {})
                    if "ActiveAccessPoint" in changed:
                        self._snapshot()
                elif ifaceName == AP_IF:
                    with self._lock:
                        active = self._activeAp == path
                    if "Strength" in changed and active:
                        self._maybeRssiChanged(path, changed.get("Strength"))
            except Exception as e:
                logging.error("NMWifiBackend: props cb fail: %s" % e)

        def onAPList(conn, sender, path, iface, signal, params):
            try:
                with self._lock:
                    dev = self._device
                if dev is not None and path != dev:
                    return
                self._scheduleApListEmit()
            except Exception as e:
                logging.error("NMWifiBackend: AP list cb fail: %s" % e)

        def onActiveState(conn, sender, path, iface, signal, params):
            try:
                state = int(params.unpack()[0])
                self._snapshot()
                connectedNow = (state == NM_ACT_STATE_ACTIVATED)
                with self._lock:
                    prevCon = self._connActive
                    self._connActive = connectedNow
                    active = self._activeConn
                if prevCon == connectedNow:
                    return
                if connectedNow:
                    self._emit(Event.CONNECTION_CHANGED,
                               {"connected": True, "ssid": (active or {}).get("ssid"),
                                "id": (active or {}).get("id")})
                else:
                    self._emit(Event.CONNECTION_CHANGED, {"connected": False})
            except Exception as e:
                logging.error("NMWifiBackend: active state cb fail: %s" % e)

        def onDeviceHotplug(conn, sender, path, iface, signal, params):
            try:
                self._snapshot()
            except Exception as e:
                logging.error("NMWifiBackend: device hotplug cb fail: %s" % e)

        bus = self._bus
        bus.signal_subscribe(NM, NM_IF, "DeviceAdded", None, None,
                             Gio.DBusSignalFlags.NONE, onDeviceHotplug)
        bus.signal_subscribe(NM, NM_IF, "DeviceRemoved", None, None,
                             Gio.DBusSignalFlags.NONE, onDeviceHotplug)
        bus.signal_subscribe(NM, PROPS_IF, "PropertiesChanged", None, None,
                             Gio.DBusSignalFlags.NONE, onPropertiesChanged)
        bus.signal_subscribe(NM, WIFI_IF, "AccessPointAdded", None, None,
                             Gio.DBusSignalFlags.NONE, onAPList)
        bus.signal_subscribe(NM, WIFI_IF, "AccessPointRemoved", None, None,
                             Gio.DBusSignalFlags.NONE, onAPList)
        bus.signal_subscribe(NM, ACT_IF, "StateChanged", None, None,
                             Gio.DBusSignalFlags.NONE, onActiveState)

    def _emit(self, evt: Event, data: dict):
        if self._onEvent is not None:
            try:
                self._onEvent(int(evt), json.dumps(data, ensure_ascii=False))
            except Exception as e:
                logging.error("NMWifiBackend: _emit fail: %s" % e)

    def _cancelApListEmit(self):
        self._apListGen += 1

    def _scheduleApListEmit(self):
        self._apListGen += 1
        gen = self._apListGen

        def fire():
            if (not self._stopping) and gen == self._apListGen:
                self._emit(Event.SCAN_RESULTS_AVAILABLE, {})
            return False

        src = GLib.timeout_source_new(AP_LIST_EMIT_DELAY_MS)
        src.set_callback(fire)
        src.attach(self._ctx)

    def _maybeRssiChanged(self, path, strength):
        try:
            now = time.time()
            lastPath, lastStr, lastTs = self._lastRssi
            if strength is None:
                return
            s = int(strength)
            if lastStr is None:
                pass
            elif path != lastPath:
                pass
            elif s == lastStr:
                return
            elif abs(s - lastStr) >= RSSI_EMIT_MIN_DELTA:
                pass
            elif now - lastTs >= RSSI_EMIT_MIN_INTERVAL:
                pass
            else:
                return
            self._lastRssi = (path, s, now)
            self._emit(Event.RSSI_CHANGED, {"strength": s})
        except Exception as e:
            logging.error("NMWifiBackend: _maybeRssiChanged fail: %s" % e)

    def currentStateEvents(self):
        with self._lock:
            enabled = bool(self._enabled)
            conn = self._activeConn
        out = [(Event.WIFI_STATE_CHANGED, {"enabled": enabled})]
        if conn:
            out.append((Event.CONNECTION_CHANGED, {
                "connected": True, "ssid": conn.get("ssid"), "id": conn.get("id")}))
        else:
            out.append((Event.CONNECTION_CHANGED, {"connected": False}))
        return out

    def isEnabled(self) -> bool:
        with self._lock:
            return bool(self._enabled)

    def setEnabled(self, on: bool) -> bool:
        with self._lock:
            fake = self._fake
        if fake:
            return True
        try:
            self._setProp("WirelessEnabled", GLib.Variant("b", bool(on)))
            return True
        except Exception as e:
            logging.error("NMWifiBackend: setEnabled fail: %s" % e)
            return False

    def startScan(self) -> bool:
        with self._lock:
            fake = self._fake
            dev = self._device
        if fake:
            return True
        if not dev:
            return False
        try:
            self._call(dev, WIFI_IF, "RequestScan", GLib.Variant("(a{sv})", ({},)), 10000)
            return True
        except Exception as e:
            msg = str(e).lower()
            if ("in progress" in msg or "already" in msg
                    or "following previous scan" in msg or "not allowed" in msg):
                logging.info("NMWifiBackend: startScan throttled/already, treating as accepted")
                return True
            logging.error("NMWifiBackend: startScan fail: %s" % e)
            return False

    def getConnectionInfo(self) -> str:
        with self._lock:
            fake = self._fake
        if fake:
            return json.dumps({
                "enabled": True, "hw": True, "connected": True,
                "ssid": FAKE_SSID, "bssid": FAKE_AP_MAC, "freq": FAKE_FREQ,
                "strength": FAKE_STRENGTH, "rssiDbm": FAKE_RSSI_DBM,
                "bitrateMbps": FAKE_BITRATE, "ifname": FAKE_IFNAME, "state": FAKE_STATE,
                "deviceMac": FAKE_DEV_MAC,
            }, ensure_ascii=False)
        root = self._getAll(NM_PATH, NM_IF)
        info = {
            "enabled": bool(root.get("WirelessEnabled")),
            "hw": bool(root.get("WirelessHardwareEnabled")),
            "connected": False,
            "ssid": None, "bssid": None, "freq": 0, "strength": 0, "rssiDbm": -100,
            "bitrateMbps": 0, "ifname": None, "state": (root.get("State")),
            "deviceMac": None,
        }
        with self._lock:
            dev = self._device
            active = self._activeConn
            ifname = self._ifname
        if dev:
            info["ifname"] = ifname
            w = self._getAll(dev, WIFI_IF)
            info["deviceMac"] = w.get("HwAddress")
            info["bitrateMbps"] = round((w.get("Bitrate") or 0) / 1000.0, 1)
            ap = w.get("ActiveAccessPoint")
            if ap and ap != "/":
                app = self._getAll(ap, AP_IF)
                info["connected"] = True
                info["bssid"] = app.get("HwAddress")
                info["freq"] = app.get("Frequency")
                info["strength"] = app.get("Strength")
                info["rssiDbm"] = round((info["strength"] or 0) * 0.7 - 100)
                info["ssid"] = _ssid(app)
        if active and active.get("id"):
            info["connected"] = True
            info["ssid"] = info["ssid"] or active.get("ssid")
        return json.dumps(info, ensure_ascii=False)

    def getScanResults(self) -> str:
        with self._lock:
            fake = self._fake
            dev = self._device
        if fake:
            return json.dumps({"results": [{
                "ssid": FAKE_SSID, "bssid": FAKE_AP_MAC, "freq": FAKE_FREQ,
                "strength": FAKE_STRENGTH, "rssiDbm": FAKE_RSSI_DBM,
                "wpaFlags": 0x108, "rsnFlags": 0x108, "security": FAKE_SECURITY,
                "lastSeen": 0,
            }]}, ensure_ascii=False)
        out = {"results": []}
        if not dev:
            return json.dumps(out, ensure_ascii=False)
        try:
            aps = _py(self._call(dev, WIFI_IF, "GetAllAccessPoints", None).unpack()[0]) or []
        except Exception as e:
            logging.error("NMWifiBackend: GetAllAccessPoints fail: %s" % e)
            return json.dumps(out, ensure_ascii=False)
        for p in aps:
            a = self._getAll(p, AP_IF)
            out["results"].append({
                "ssid": _ssid(a),
                "bssid": a.get("HwAddress"),
                "freq": a.get("Frequency"),
                "strength": a.get("Strength"),
                "wpaFlags": a.get("WpaFlags"),
                "rsnFlags": a.get("RsnFlags"),
                "security": _security(a.get("WpaFlags"), a.get("RsnFlags")),
                "lastSeen": a.get("LastSeen"),
            })
        out["results"].sort(key=lambda r: (r.get("strength") or -200), reverse=True)
        return json.dumps(out, ensure_ascii=False)

    def _savedConnections(self):
        try:
            conns = _py(self._call(NM_SETTINGS_PATH, NM_SETTINGS_IF, "ListConnections", None).unpack()[0]) or []
        except Exception as e:
            logging.error("NMWifiBackend: ListConnections fail: %s" % e)
            return []
        out = []
        for c in conns:
            if not c or c == "/":
                continue
            try:
                settings = _py(self._call(c, SETCON_IF, "GetSettings", None).unpack()[0]) or {}
            except Exception as e:
                logging.error("NMWifiBackend: GetSettings(conn=%s) fail: %s" % (c, e))
                continue
            if (settings.get("connection") or {}).get("type") != "802-11-wireless":
                continue
            out.append({"path": c,
                        "id": (settings.get("connection") or {}).get("id"),
                        "ssid": _settingsSsid(settings.get("802-11-wireless") or {})})
        return out

    def getSavedNetworks(self) -> str:
        with self._lock:
            fake = self._fake
        if fake:
            return json.dumps({"networks": []}, ensure_ascii=False)
        nets = [{"name": n.get("id"), "ssid": n.get("ssid")} for n in self._savedConnections()]
        return json.dumps({"networks": nets}, ensure_ascii=False)

    @staticmethod
    def _buildSettings(ssid, security, passphrase):
        s = {
            "connection": {"id": GLib.Variant("s", ssid or ""),
                           "type": GLib.Variant("s", "802-11-wireless"),
                           "autoconnect": GLib.Variant("b", True)},
            "802-11-wireless": {"ssid": GLib.Variant("ay", (ssid or "").encode("utf-8")),
                                "mode": GLib.Variant("s", "infrastructure")},
        }
        if security == SECURITY_WPA2_PSK:
            s["802-11-wireless"]["security"] = GLib.Variant("s", "802-11-wireless-security")
            s["802-11-wireless-security"] = {"key-mgmt": GLib.Variant("s", "wpa-psk"),
                                             "psk": GLib.Variant("s", passphrase or "")}
        elif security == SECURITY_SAE:
            s["802-11-wireless"]["security"] = GLib.Variant("s", "802-11-wireless-security")
            s["802-11-wireless-security"] = {"key-mgmt": GLib.Variant("s", "sae"),
                                             "psk": GLib.Variant("s", passphrase or "")}
        return s

    def connect(self, ssid, security, passphrase) -> bool:
        with self._lock:
            dev = self._device
            fake = self._fake
        if fake or not dev:
            return False
        try:
            for n in self._savedConnections():
                if str(n.get("ssid")) == str(ssid):
                    self._call(NM_PATH, NM_IF, "ActivateConnection",
                               GLib.Variant("(ooo)", (n["path"], dev, "/")), 15000)
                    return True
            settings = self._buildSettings(ssid, security, passphrase)
            newConn = _py(self._call(NM_SETTINGS_PATH, NM_SETTINGS_IF, "AddConnection",
                                      GLib.Variant("(a{sa{sv}})", (settings,)), 15000).unpack()[0])
            self._call(NM_PATH, NM_IF, "ActivateConnection",
                       GLib.Variant("(ooo)", (newConn, dev, "/")), 15000)
            return True
        except Exception as e:
            logging.error("NMWifiBackend: connect(%s) fail: %s" % (ssid, e))
            return False

    def connectSaved(self, name) -> bool:
        with self._lock:
            dev = self._device
            fake = self._fake
        if fake or not dev:
            return False
        try:
            for n in self._savedConnections():
                if str(n.get("id")) == str(name):
                    self._call(NM_PATH, NM_IF, "ActivateConnection",
                               GLib.Variant("(ooo)", (n["path"], dev, "/")), 15000)
                    return True
            logging.warning("NMWifiBackend: connectSaved: no saved conn named %r" % name)
            return False
        except Exception as e:
            logging.error("NMWifiBackend: connectSaved(%s) fail: %s" % (name, e))
            return False

    def disconnect(self) -> bool:
        with self._lock:
            dev = self._device
        if not dev:
            return False
        root = self._getAll(NM_PATH, NM_IF)
        for ac in root.get("ActiveConnections", []):
            ap = self._getAll(ac, ACT_IF)
            if ap.get("Type") != "802-11-wireless":
                continue
            if dev not in ap.get("Devices", []):
                continue
            try:
                self._call(NM_PATH, NM_IF, "DeactivateConnection",
                           GLib.Variant("(o)", (ac,)), 10000)
                return True
            except Exception as e:
                logging.error("NMWifiBackend: disconnect fail: %s" % e)
                return False
        return False

    def saveNetwork(self, ssid, security, passphrase) -> bool:
        with self._lock:
            fake = self._fake
        if fake:
            return False
        try:
            settings = self._buildSettings(ssid, security, passphrase)
            self._call(NM_SETTINGS_PATH, NM_SETTINGS_IF, "AddConnection",
                       GLib.Variant("(a{sa{sv}})", (settings,)), 15000)
            return True
        except Exception as e:
            logging.error("NMWifiBackend: saveNetwork(%s) fail: %s" % (ssid, e))
            return False

    def forgetNetwork(self, name) -> bool:
        try:
            for n in self._savedConnections():
                if str(n.get("id")) == str(name):
                    self._call(n["path"], SETCON_IF, "Delete", None, 10000)
                    return True
            return False
        except Exception as e:
            logging.error("NMWifiBackend: forgetNetwork(%s) fail: %s" % (name, e))
            return False

    def getFactoryMacAddresses(self) -> str:
        with self._lock:
            fake = self._fake
            ifname = self._ifname
            dev = self._device
        if fake:
            return json.dumps({FAKE_IFNAME: FAKE_DEV_MAC}, ensure_ascii=False)
        if not dev or not ifname:
            return json.dumps({}, ensure_ascii=False)
        try:
            w = self._getAll(dev, WIFI_IF)
            mac = w.get("HwAddress")
            if not mac:
                return json.dumps({}, ensure_ascii=False)
            return json.dumps({ifname: mac}, ensure_ascii=False)
        except Exception as e:
            logging.error("NMWifiBackend: getFactoryMacAddresses fail: %s" % e)
            return json.dumps({}, ensure_ascii=False)

    def getDhcpInfo(self) -> str:
        with self._lock:
            fake = self._fake
            dev = self._device
        if fake:
            dns = FAKE_DHCP_DNS
            return json.dumps({
                "ip": FAKE_DHCP_IP, "gateway": FAKE_DHCP_GW, "netmask": FAKE_DHCP_NETMASK,
                "dns1": dns[0], "dns2": dns[1] if len(dns) > 1 else "",
                "server": FAKE_DHCP_GW, "lease": FAKE_DHCP_LEASE}, ensure_ascii=False)
        if not dev:
            return json.dumps({}, ensure_ascii=False)
        root = self._getAll(NM_PATH, NM_IF)
        for ac in root.get("ActiveConnections", []):
            ap = self._getAll(ac, ACT_IF)
            if ap.get("Type") != "802-11-wireless" or dev not in ap.get("Devices", []):
                continue
            ip4 = ap.get("Ip4Config")
            if not ip4 or ip4 == "/":
                continue
            try:
                cfg = self._getAll(ip4, IP4_IF)
                addrData = cfg.get("AddressData") or []
                address = _ip4ToDotted((addrData[0] or {}).get("address")) if addrData else None
                prefix = (addrData[0] or {}).get("prefix") if addrData else None
                gw = _ip4ToDotted(cfg.get("Gateway"))
                dns = [_ip4ToDotted(d) for d in (cfg.get("Nameservers") or [])]
                dns = [d for d in dns if d]
                if not address:
                    return json.dumps({}, ensure_ascii=False)
                return json.dumps({
                    "ip": address,
                    "gateway": gw or "0.0.0.0",
                    "netmask": _prefixToNetmask(prefix) if prefix is not None else "255.255.255.0",
                    "dns1": dns[0] if dns else "0.0.0.0",
                    "dns2": dns[1] if len(dns) > 1 else "0.0.0.0",
                    "server": gw or "0.0.0.0",
                    "lease": 86400,
                }, ensure_ascii=False)
            except Exception as e:
                logging.error("NMWifiBackend: getDhcpInfo fail: %s" % e)
                return json.dumps({}, ensure_ascii=False)
        return json.dumps({}, ensure_ascii=False)

    def cleanup(self):
        self._stopping = True
        try:
            self._ctx.invoke_full(GLib.PRIORITY_DEFAULT,
                                  lambda: (self._loop.quit(), False)[1])
        except Exception:
            pass
        logging.debug("NMWifiBackend: cleanup done")
