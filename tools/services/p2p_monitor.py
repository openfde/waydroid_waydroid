# P2P event monitor: a minimal persistent wpa_cli replacement.
#
# Attaches to the wpa_supplicant global control socket (falling back to the
# first per-interface socket), receives unsolicited events, parses the P2P
# ones and forwards them to registered binder callbacks through the
# dispatch function handed in by p2p_manager.

import logging
import os
import re
import selectors
import socket
import tempfile
import threading
import time
from pathlib import Path

from tools.interfaces import p2p_callback


_RETRY_DELAY = 3.0
_KV_RE = re.compile(r"(\w+)=('([^']*)'|\"([^\"]*)\"|[^\s]+)")
_PREFIX_RE = re.compile(r"^<\d+>")

DEFAULT_CTRL_DIRS = (
    "/run/wpa_supplicant",
    "/var/run/wpa_supplicant",
)


class WpaCtrlSocket:
    def __init__(self, ctrl_path):
        self.ctrl_path = ctrl_path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._local_path = None
        self._selector = selectors.DefaultSelector()

    def open(self):
        if self._local_path is None:
            tmp_dir = Path(tempfile.gettempdir())
            self._local_path = str(
                tmp_dir / "wpa_ctrl_py_{}_{}".format(os.getpid(),
                                                     int(time.time() * 1000)))
        try:
            os.unlink(self._local_path)
        except FileNotFoundError:
            pass
        self.sock.bind(self._local_path)
        self.sock.connect(self.ctrl_path)
        self.sock.setblocking(False)
        self._selector.register(self.sock, selectors.EVENT_READ)

    def send_command(self, command):
        self.sock.send(command.encode("utf-8"))
        return self._read_reply(timeout=5.0)

    def read_event(self, timeout):
        events = self._selector.select(timeout)
        if not events:
            return None
        try:
            data = self.sock.recv(4096)
        except BlockingIOError:
            return None
        if not data:
            return None
        return data.decode("utf-8", errors="replace").rstrip("\r\n")

    def close(self):
        try:
            self._selector.unregister(self.sock)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        if self._local_path:
            try:
                os.unlink(self._local_path)
            except FileNotFoundError:
                pass

    def _read_reply(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            events = self._selector.select(remaining)
            if not events:
                continue
            try:
                data = self.sock.recv(4096)
            except BlockingIOError:
                continue
            if not data:
                continue
            text = data.decode("utf-8", errors="replace").rstrip("\r\n")
            if text in {"OK", "FAIL"}:
                return text
        raise TimeoutError("timed out waiting for reply")


def _find_ctrl_path():
    for base in DEFAULT_CTRL_DIRS:
        candidate = os.path.join(base, 'global')
        if os.path.exists(candidate):
            return candidate
    for base in DEFAULT_CTRL_DIRS:
        path = Path(base)
        if not path.is_dir():
            continue
        for entry in sorted(path.iterdir()):
            if entry.is_socket() or entry.is_file():
                return str(entry)
    return None


def _to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value, 0)
    except (ValueError, TypeError):
        return default


def _hex_to_bytes(value):
    if not value:
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        return None


def _parse_kv(text):
    fields = {}
    for match in _KV_RE.finditer(text):
        value = match.group(3)
        if value is None:
            value = match.group(4)
        if value is None:
            value = match.group(2)
        fields[match.group(1)] = value
    return fields


def _parse_dev_type(value):
    """'10-0050F204-5' -> 8-byte WPS primary device type."""
    if not value:
        return None
    parts = value.split('-')
    if len(parts) != 3:
        return None
    try:
        category = int(parts[0])
        oui = int(parts[1], 16)
        subcategory = int(parts[2])
    except ValueError:
        return None
    return (category.to_bytes(2, 'big') + oui.to_bytes(4, 'big')
            + subcategory.to_bytes(2, 'big'))


class P2pEventMonitor:
    def __init__(self, dispatch):
        self._dispatch = dispatch
        self._stopping = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stopping.set()

    def _run(self):
        while not self._stopping.is_set():
            ctrl_path = _find_ctrl_path()
            if not ctrl_path:
                self._stopping.wait(_RETRY_DELAY)
                continue

            ctrl = WpaCtrlSocket(ctrl_path)
            try:
                ctrl.open()
                if ctrl.send_command('ATTACH') != 'OK':
                    raise OSError("ATTACH failed on {}".format(ctrl_path))
                logging.info("P2P event monitor attached to %s", ctrl_path)
                self._listen(ctrl)
            except Exception as e:
                logging.error("P2P event monitor error on %s: %s", ctrl_path, e)
            finally:
                ctrl.close()
            self._stopping.wait(_RETRY_DELAY)

    def _listen(self, ctrl):
        while not self._stopping.is_set():
            line = ctrl.read_event(timeout=0.5)
            if not line:
                continue
            try:
                self._handle_event(line)
            except Exception as e:
                logging.error("Failed to handle supplicant event %r: %s", line, e)

    def _handle_event(self, line):
        ifname = None
        if line.startswith('IFNAME='):
            ifname, _, line = line.partition(' ')
            ifname = ifname[len('IFNAME='):]
        line = _PREFIX_RE.sub('', line).strip()

        if line.startswith('P2P-DEVICE-FOUND'):
            self._on_device_found(line)
        elif line.startswith('P2P-DEVICE-LOST'):
            fields = _parse_kv(line)
            self._dispatch('onDeviceLost', fields.get('p2p_device_address'))
        elif line.startswith('P2P-FIND-STOPPED'):
            self._dispatch('onFindStopped')
        elif line.startswith('P2P-GO-NEG-REQUEST'):
            tokens = line.split(None, 2)
            fields = _parse_kv(tokens[2] if len(tokens) > 2 else '')
            self._dispatch('onGoNegotiationRequestWithParams',
                           tokens[1] if len(tokens) > 1 else None,
                           _to_int(fields.get('dev_passwd_id')),
                           _to_int(fields.get('go_intent')))
        elif line.startswith('P2P-GO-NEG-SUCCESS'):
            self._dispatch('onGoNegotiationCompleted',
                           int(p2p_callback.P2pStatusCode.SUCCESS))
        elif line.startswith('P2P-GO-NEG-FAILURE'):
            fields = _parse_kv(line)
            self._dispatch('onGoNegotiationCompleted',
                           _to_int(fields.get('status'),
                                   int(p2p_callback.P2pStatusCode.UNKNOWN_ERROR)))
        elif line.startswith('P2P-GROUP-FORMATION-SUCCESS'):
            self._dispatch('onGroupFormationSuccess')
        elif line.startswith('P2P-GROUP-FORMATION-FAILURE'):
            reason = line[len('P2P-GROUP-FORMATION-FAILURE'):].strip()
            self._dispatch('onGroupFormationFailure', reason)
        elif line.startswith('P2P-GROUP-STARTED'):
            self._on_group_started(line)
        elif line.startswith('P2P-GROUP-REMOVED'):
            tokens = line.split()
            ifname_arg = tokens[1] if len(tokens) > 1 else ""
            role = tokens[2] if len(tokens) > 2 else ""
            self._dispatch('onGroupRemoved', ifname_arg, role == 'GO')
        elif line.startswith('P2P-INVITATION-RECEIVED'):
            fields = _parse_kv(line)
            self._dispatch('onInvitationReceivedWithParams',
                           fields.get('sa'), fields.get('go_dev_addr'),
                           fields.get('bssid'),
                           _to_int(fields.get('persistent'), -1),
                           _to_int(fields.get('freq')))
        elif line.startswith('P2P-INVITATION-RESULT'):
            fields = _parse_kv(line)
            self._dispatch('onInvitationResult', fields.get('bssid'),
                           _to_int(fields.get('status'),
                                   int(p2p_callback.P2pStatusCode.UNKNOWN_ERROR)))
        elif line.startswith('P2P-PROV-DISC-'):
            self._on_prov_disc(line)
        elif line.startswith('P2P-SERV-DISC-RESP'):
            tokens = line.split()
            src = tokens[1] if len(tokens) > 1 else None
            update = tokens[2] if len(tokens) > 2 else '0'
            tlvs = tokens[3] if len(tokens) > 3 else None
            self._dispatch('onServiceDiscoveryResponse', src, _to_int(update),
                           _hex_to_bytes(tlvs))
        elif line.startswith('AP-STA-CONNECTED'):
            if ifname is None or ifname.startswith('p2p'):
                self._on_sta(line, joined=True)
        elif line.startswith('AP-STA-DISCONNECTED'):
            if ifname is None or ifname.startswith('p2p'):
                self._on_sta(line, joined=False)

    def _on_device_found(self, line):
        tokens = line.split(None, 1)
        src = tokens[1].split(None, 1)[0] if len(tokens) > 1 else None
        fields = _parse_kv(tokens[1] if len(tokens) > 1 else '')
        wfd = _hex_to_bytes(fields.get('wfd_dev_info'))
        wfd_r2 = _hex_to_bytes(fields.get('wfd_r2_dev_info'))
        vendor = _hex_to_bytes(fields.get('vendor_elems'))
        common = (src,
                  fields.get('p2p_dev_addr', src),
                  _parse_dev_type(fields.get('pri_dev_type')),
                  fields.get('name', ''),
                  _to_int(fields.get('config_methods')),
                  _to_int(fields.get('dev_capab')),
                  _to_int(fields.get('group_capab')),
                  wfd)
        if wfd_r2 is not None:
            self._dispatch('onR2DeviceFound', *common, wfd_r2)
        elif vendor is not None:
            self._dispatch('onDeviceFoundWithVendorElements', *common, None, vendor)
        else:
            self._dispatch('onDeviceFound', *common)

    def _on_group_started(self, line):
        tokens = line.split(None, 3)
        group_ifname = tokens[1] if len(tokens) > 1 else ""
        role = tokens[2] if len(tokens) > 2 else ""
        fields = _parse_kv(tokens[3] if len(tokens) > 3 else '')
        ssid = fields.get('ssid', '')
        self._dispatch('onGroupStartedWithParams',
                       group_ifname,
                       role == 'GO',
                       ssid.encode('utf-8') if ssid else None,
                       _to_int(fields.get('freq')),
                       _hex_to_bytes(fields.get('psk')),
                       fields.get('passphrase', ''),
                       fields.get('go_dev_addr'),
                       'PERSISTENT' in line)

    def _on_prov_disc(self, line):
        tokens = line.split()
        address = tokens[1] if len(tokens) > 1 else None
        methods = p2p_callback.WpsConfigMethods
        status = p2p_callback.P2pProvDiscStatusCode
        if line.startswith('P2P-PROV-DISC-PBC-REQ'):
            self._dispatch('onProvisionDiscoveryCompletedEvent', address,
                           int(status.SUCCESS), int(methods.PUSH_BUTTON), "")
        elif line.startswith('P2P-PROV-DISC-PBC-RESP'):
            self._dispatch('onProvisionDiscoveryCompletedEvent', address,
                           int(status.SUCCESS), int(methods.PUSH_BUTTON), "")
        elif line.startswith('P2P-PROV-DISC-ENTER-PIN'):
            self._dispatch('onProvisionDiscoveryCompletedEvent', address,
                           int(status.SUCCESS), int(methods.KEYPAD), "")
        elif line.startswith('P2P-PROV-DISC-SHOW-PIN'):
            pin = tokens[2] if len(tokens) > 2 else ""
            self._dispatch('onProvisionDiscoveryCompletedEvent', address,
                           int(status.SUCCESS), int(methods.DISPLAY), pin)
        elif line.startswith('P2P-PROV-DISC-FAILURE'):
            self._dispatch('onProvisionDiscoveryCompletedEvent', address,
                           int(status.REJECTED), 0, "")

    def _on_sta(self, line, joined):
        tokens = line.split(None, 2)
        address = tokens[1] if len(tokens) > 1 else None
        fields = _parse_kv(tokens[2] if len(tokens) > 2 else '')
        p2p_addr = fields.get('p2p_dev_addr', address)
        if joined:
            self._dispatch('onPeerClientJoined', address, p2p_addr, False)
        else:
            self._dispatch('onPeerClientDisconnected', address, p2p_addr)
