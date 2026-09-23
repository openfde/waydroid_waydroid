# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import binascii
import json
import logging
import re
import shlex
import subprocess
import threading

from tools.interfaces import IP2p, ISupplicantP2pNetwork, p2p_callback
from tools.services.p2p_monitor import P2pEventMonitor


initData = {
    'controller': None,
    'monitor': None,
    'stopping': False,
    'network_service_started': False,
}

callbackData = {
    'INTERFACE': p2p_callback.INTERFACE,
    'lock': threading.Lock(),
    'registeredCallbacks': [],
    'deathNotifications': {}
}


P2P_EVENT_CODES = {
    'onDeviceFound': 1,
    'onDeviceLost': 2,
    'onFindStopped': 3,
    'onGoNegotiationCompleted': 4,
    'onGoNegotiationRequest': 5,
    'onGroupFormationFailure': 6,
    'onGroupFormationSuccess': 7,
    'onGroupRemoved': 8,
    'onGroupStarted': 9,
    'onInvitationReceived': 10,
    'onInvitationResult': 11,
    'onProvisionDiscoveryCompleted': 12,
    'onR2DeviceFound': 13,
    'onServiceDiscoveryResponse': 14,
    'onStaAuthorized': 15,
    'onStaDeauthorized': 16,
    'onGroupFrequencyChanged': 17,
    'onDeviceFoundWithVendorElements': 18,
    'onGroupStartedWithParams': 19,
    'onPeerClientJoined': 20,
    'onPeerClientDisconnected': 21,
    'onProvisionDiscoveryCompletedEvent': 22,
    'onDeviceFoundWithParams': 23,
    'onGoNegotiationRequestWithParams': 24,
    'onInvitationReceivedWithParams': 25,
    'onUsdBasedServiceDiscoveryResult': 26,
    'onUsdBasedServiceDiscoveryTerminated': 27,
    'onUsdBasedServiceAdvertisementTerminated': 28,
}


def _event_value(value):
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def dispatch_event(method_name, *args):
    """Send one string-only P2P event to every registered callback."""
    event_code = P2P_EVENT_CODES.get(method_name)
    if event_code is None:
        logging.error("Unknown P2P callback event: %s", method_name)
        return
    data = json.dumps({
        'event': method_name,
        'args': [_event_value(arg) for arg in args],
    })
    with callbackData['lock']:
        callbacks = list(callbackData['registeredCallbacks'])
    for callback in callbacks:
        try:
            if callback.is_dead():
                logging.warning("P2P callback is dead, skipping %s", method_name)
                continue
            proxy = p2p_callback.ISupplicantP2pIfaceCallback(callback)
            proxy.onEvents(event_code, data)
        except Exception as e:
            logging.error("Failed to dispatch %s to P2P callback %s: %s",
                          method_name, callback, e)


class P2pController:
    P2P_GLOBAL_CONFIG_VARS = {
        'device_name', 'device_type', 'config_methods', 'uuid', 'serial_number',
        'manufacturer', 'model_name', 'model_number', 'os_version',
        'p2p_listen_reg_class', 'p2p_listen_channel',
        'p2p_oper_reg_class', 'p2p_oper_channel', 'p2p_go_intent',
        'p2p_ssid_postfix', 'persistent_reconnect', 'p2p_intra_bss',
        'p2p_group_idle', 'p2p_passphrase_len', 'p2p_search_delay',
    }

    P2P_SET_ALIASES = {
        'ssid_postfix': 'p2p_ssid_postfix',
        'listen_channel': 'p2p_listen_channel',
        'listen_reg_class': 'p2p_listen_reg_class',
        'go_intent': 'p2p_go_intent',
    }

    NM_IGNORED_P2P_SET_VARS = {
        'group_idle',
        'random_mac',
        'disallow_freq',
    }

    def __init__(self):
        self.interface = None
        self.active_connection_name = None
        self.active_peer = None
        self.active_group_ifname = None
        self.active_is_go = False
        self.active_ssid = ""
        self.active_bssid = ""
        self.active_client_list = ""

    def _run_wpa_cli(self, *args):
        command = ['wpa_cli']
        if self.interface:
            command.extend(['-i', self.interface])
        if any(arg.startswith('-') for arg in args):
            command.append('--')
        command.extend(args)
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        except FileNotFoundError:
            logging.error("wpa_cli not found")
            return None
        except subprocess.TimeoutExpired:
            logging.error("wpa_cli command timed out: %s", " ".join(command))
            return None

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            if stderr:
                logging.error("wpa_cli failed: %s", stderr)
            else:
                logging.error("wpa_cli failed with exit code %s", result.returncode)
            return None
        if stderr:
            logging.debug("wpa_cli stderr: %s", stderr)
        return stdout

    def _run_wpa_cli_for_interface(self, interface, *args):
        command = ['wpa_cli', '-i', interface]
        if any(arg.startswith('-') for arg in args):
            command.append('--')
        command.extend(args)
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        except FileNotFoundError:
            logging.error("wpa_cli not found")
            return None
        except subprocess.TimeoutExpired:
            logging.error("wpa_cli command timed out: %s", " ".join(command))
            return None

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            logging.error("wpa_cli failed (%s): %s", " ".join(command), stderr or result.returncode)
            return None
        return stdout

    def _run_nmcli(self, *args, timeout=30):
        command = ['nmcli']
        command.extend(args)
        logging.info("Running nmcli command: %s", " ".join(command))
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        except FileNotFoundError:
            logging.error("nmcli not found")
            return None
        except subprocess.TimeoutExpired:
            logging.error("nmcli command timed out: %s", " ".join(command))
            return None

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            logging.error("nmcli failed (%s): %s", " ".join(command), stderr or result.returncode)
            return None
        logging.info("nmcli succeeded (%s): %s", " ".join(command), stdout)
        if stderr:
            logging.debug("nmcli stderr: %s", stderr)
        return stdout

    def _parse_peer_mac(self, raw_args):
        logging.warning("Parsing P2P connect args for peer MAC: %s", raw_args)
        for token in shlex.split(raw_args or ""):
            if re.fullmatch(r'[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}', token):
                peer = token.lower()
                logging.warning("Parsed P2P peer MAC: %s", peer)
                return peer
        logging.error("No P2P peer MAC found in args: %s", raw_args)
        return None

    def _p2p_peer_exists(self, peer):
        output = self.p2p_peer(peer)
        logging.info("wpa_cli p2p_peer %s output: %s", peer, output)
        return bool(output and output != 'FAIL')

    def _nm_connection_name(self, peer):
        return "wifi-p2p"

    def _nm_saved_p2p_connections(self):
        output = self._run_nmcli('-t', '-f', 'NAME,TYPE', 'connection', 'show')
        if not output:
            logging.info("No saved NetworkManager connections found while searching for wifi-p2p profiles")
            return []
        names = []
        for line in output.splitlines():
            fields = line.rsplit(':', 1)
            if len(fields) != 2:
                continue
            name, conn_type = fields
            if conn_type == 'wifi-p2p':
                names.append(name)
        logging.info("Saved NetworkManager wifi-p2p connections: %s", names)
        return names

    def _nm_connection_peer(self, name):
        output = self._run_nmcli('-g', 'wifi-p2p.peer', 'connection', 'show', name)
        peer = output.strip().lower() if output else ""
        logging.info("NetworkManager connection %s has wifi-p2p.peer=%s", name, peer)
        return peer

    def _nm_find_p2p_connection(self, peer):
        fallback = None
        for name in self._nm_saved_p2p_connections():
            configured_peer = self._nm_connection_peer(name)
            if configured_peer == peer:
                logging.info("Selected exact NetworkManager P2P connection %s for peer %s", name, peer)
                return name
            if fallback is None:
                fallback = name
            if name == 'wifi-p2p':
                fallback = name
        logging.info("Selected fallback NetworkManager P2P connection %s for peer %s", fallback, peer)
        return fallback

    def _nm_connection_exists(self, name):
        return self._run_nmcli('connection', 'show', name) is not None

    def _nm_ensure_p2p_connection(self, name, peer):
        if self._nm_connection_exists(name):
            logging.warning("Updating existing NetworkManager P2P connection %s for peer %s", name, peer)
            output = self._run_nmcli(
                'connection', 'modify', name,
                'wifi-p2p.peer', peer,
                'ipv4.method', 'auto')
            logging.warning("NetworkManager P2P connection modify result for %s: %s", name, output)
            return output is not None
        logging.warning("Creating NetworkManager P2P connection %s for peer %s", name, peer)
        output = self._run_nmcli(
            'connection', 'add',
            'type', 'wifi-p2p',
            'wifi-p2p.peer', peer,
            'con-name', name,
            'ipv4.method', 'auto')
        logging.warning("NetworkManager P2P connection add result for %s: %s", name, output)
        if output is not None:
            return True

        logging.warning("Retrying NetworkManager P2P connection creation after deleting stale profile %s", name)
        self._run_nmcli('connection', 'delete', name)
        output = self._run_nmcli(
            'connection', 'add',
            'type', 'wifi-p2p',
            'wifi-p2p.peer', peer,
            'con-name', name,
            'ipv4.method', 'auto')
        logging.info("NetworkManager P2P connection recreate result for %s: %s", name, output)
        return output is not None

    def _nm_active_p2p_connections(self):
        output = self._run_nmcli('-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active')
        if not output:
            return []
        active = []
        for line in output.splitlines():
            fields = line.rsplit(':', 2)
            if len(fields) < 3:
                continue
            name, conn_type, device = fields[0], fields[1], fields[2]
            if conn_type == 'wifi-p2p':
                active.append((name, device))
        return active

    def _refresh_active_p2p_connection(self, preferred_name=None, peer=None):
        active = self._nm_active_p2p_connections()
        selected = None
        for name, device in active:
            if preferred_name is None or name == preferred_name:
                selected = (name, device)
                break
        if selected is None and active:
            selected = active[0]
        if selected is None:
            return False

        self.active_connection_name, self.active_group_ifname = selected
        if peer:
            self.active_peer = peer
        self._refresh_group_status()
        return True

    def _refresh_group_status(self):
        if not self.active_group_ifname:
            return
        status = self._run_wpa_cli_for_interface(self.active_group_ifname, 'status')
        if not status:
            return
        for line in status.splitlines():
            key, sep, value = line.partition('=')
            if not sep:
                continue
            if key == 'mode':
                self.active_is_go = value == 'P2P GO'
            elif key == 'ssid':
                self.active_ssid = value
            elif key == 'bssid':
                self.active_bssid = value

    def _clear_active_group(self):
        self.active_connection_name = None
        self.active_peer = None
        self.active_group_ifname = None
        self.active_is_go = False
        self.active_ssid = ""
        self.active_bssid = ""
        self.active_client_list = ""

    def _emit_nm_connection_success(self):
        dispatch_event('onGoNegotiationCompleted', int(p2p_callback.P2pStatusCode.SUCCESS))
        if self.active_group_ifname:
            dispatch_event(
                'onGroupStartedWithParams',
                self.active_group_ifname,
                self.active_is_go,
                self.active_ssid.encode('utf-8') if self.active_ssid else None,
                0,
                None,
                "",
                self.active_peer,
                True)

    def _emit_nm_connection_failure(self):
        dispatch_event('onGoNegotiationCompleted', int(p2p_callback.P2pStatusCode.UNKNOWN_ERROR))

    def _ensure_interface(self):
        if self.interface:
            return self.interface

        output = self._run_wpa_cli('interface')
        if not output:
            return None

        for line in output.splitlines():
            candidate = line.strip()
            match = re.search(r"'([^']+)'", candidate)
            if match:
                self.interface = match.group(1)
                break
            if candidate and not candidate.startswith(('Selected interface', 'Available interfaces')):
                self.interface = candidate
                break

        if not self.interface:
            logging.error("No wpa_cli interface available for P2P")
        return self.interface

    def _encode_service_bytes(self, value):
        if value is None:
            return ""
        if isinstance(value, memoryview):
            value = value.tobytes()
        if isinstance(value, bytearray):
            value = bytes(value)
        if isinstance(value, bytes):
            return binascii.hexlify(value).decode('ascii')
        return str(value)

    def addBonjourService(self, query, response):
        if not self._ensure_interface():
            return

        query_hex = self._encode_service_bytes(query)
        response_hex = self._encode_service_bytes(response)
        output = self._run_wpa_cli('p2p_service_add', 'bonjour', query_hex, response_hex)
        if output != 'OK':
            logging.error("Failed to add Bonjour service: %s", output)

    def _run_p2p_command(self, *args):
        if not self._ensure_interface():
            return None
        return self._run_wpa_cli(*args)

    def _run_p2p_expect_ok(self, *args):
        output = self._run_p2p_command(*args)
        if output != 'OK':
            logging.error("P2P command failed (%s): %s", " ".join(args), output)
        return output

    def addGroup(self, persistent, persistentNetworkId):
        logging.info("Ignoring p2p_group_add request; NetworkManager creates P2P group on connection up")

    def cancelConnect(self):
        if self.active_connection_name:
            self._run_nmcli('connection', 'down', self.active_connection_name)
            dispatch_event('onGroupRemoved', self.active_group_ifname or "", self.active_is_go)
            self._clear_active_group()
        else:
            self._run_p2p_expect_ok('p2p_cancel')

    def p2p_stop_find(self):
        self._run_p2p_expect_ok('p2p_stop_find')

    def p2p_asp_provision(self, raw_args):
        self._run_p2p_expect_ok('p2p_asp_provision', *raw_args.split())

    def p2p_asp_provision_resp(self, raw_args):
        self._run_p2p_expect_ok('p2p_asp_provision_resp', *raw_args.split())

    def p2p_connect(self, raw_args):
        logging.warning("P2pController.p2p_connect called with raw_args=%s", raw_args)
        peer = self._parse_peer_mac(raw_args)
        if not peer:
            logging.error("p2p_connect requires explicit peer mac in args: %s", raw_args)
            self._emit_nm_connection_failure()
            return
        if not self._p2p_peer_exists(peer):
            logging.warning("P2P peer not confirmed by wpa_cli before NetworkManager connect: %s", peer)

        connection_name = self._nm_find_p2p_connection(peer) or self._nm_connection_name(peer)
        logging.warning("Using NetworkManager P2P connection %s for peer %s", connection_name, peer)
        if not self._nm_ensure_p2p_connection(connection_name, peer):
            logging.error("Failed to create/update NetworkManager P2P connection %s", connection_name)
            self._emit_nm_connection_failure()
            return
        logging.warning("About to run NetworkManager P2P connection up: %s", connection_name)
        output = self._run_nmcli('connection', 'up', connection_name, timeout=60)
        if output is None:
            logging.error("NetworkManager P2P connection up failed: %s", connection_name)
            self._emit_nm_connection_failure()
            return
        logging.info("NetworkManager P2P connection up completed: %s output=%s", connection_name, output)
        self.active_connection_name = connection_name
        self.active_peer = peer
        self._refresh_active_p2p_connection(connection_name, peer)
        logging.info("Active NetworkManager P2P state: connection=%s peer=%s ifname=%s is_go=%s ssid=%s bssid=%s",
                     self.active_connection_name, self.active_peer, self.active_group_ifname,
                     self.active_is_go, self.active_ssid, self.active_bssid)
        self._emit_nm_connection_success()

    def p2p_listen(self, raw_args):
        args = raw_args.split() if raw_args else []
        self._run_p2p_expect_ok('p2p_listen', *args)

    def p2p_group_remove(self, ifname):
        self._refresh_active_p2p_connection(self.active_connection_name, self.active_peer)
        connection_name = self.active_connection_name
        if connection_name and (not ifname or self.active_group_ifname == ifname):
            self._run_nmcli('connection', 'down', connection_name)
            dispatch_event('onGroupRemoved', self.active_group_ifname or ifname or "", self.active_is_go)
            self._clear_active_group()
        else:
            logging.warning("No active NetworkManager P2P group to remove: %s", ifname)

    def p2p_group_member(self, ifname):
        self._run_p2p_expect_ok('p2p_group_member', ifname)

    def p2p_prov_disc(self, raw_args):
        self._run_p2p_expect_ok('p2p_prov_disc', *raw_args.split())

    def p2p_get_passphrase(self):
        output = self._run_p2p_command('p2p_get_passphrase')
        return output or ""

    def p2p_get_device_address(self):
        output = self._run_p2p_command('status')
        if not output:
            return ""
        for line in output.splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() == 'p2p_device_address':
                return value.strip()
        logging.error("p2p_device_address not found in wpa_cli status output")
        return ""

    def _get_current_network_id(self):
        output = self._run_p2p_command('list_networks')
        if not output:
            return -1
        fallback = -1
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith('network id'):
                continue
            fields = line.split('\t')
            try:
                network_id = int(fields[0])
            except (ValueError, IndexError):
                continue
            if fallback < 0:
                fallback = network_id
            flags = fields[3] if len(fields) > 3 else ''
            if '[CURRENT]' in flags:
                return network_id
        return fallback

    def _get_network_field(self, field):
        network_id = self._get_current_network_id()
        if network_id < 0:
            return ""
        output = self._run_p2p_command('get_network', str(network_id), field)
        return output or ""

    def _set_network_field(self, field, value):
        network_id = self._get_current_network_id()
        if network_id < 0:
            logging.error("No P2P network available for set_network %s", field)
            return
        self._run_p2p_expect_ok('set_network', str(network_id), field, value or "")

    def getNetworkBssid(self):
        self._refresh_group_status()
        return self.active_bssid or self._get_network_field('bssid')

    def getNetworkClientList(self):
        return self.active_client_list or self._get_network_field('p2p_client_list')

    def getNetworkId(self):
        return self._get_current_network_id()

    def getNetworkInterfaceName(self):
        if not self.active_group_ifname:
            self._refresh_active_p2p_connection(self.active_connection_name, self.active_peer)
        return self.active_group_ifname or self.interface or self._ensure_interface() or ""

    def getNetworkSsid(self):
        self._refresh_group_status()
        return self.active_ssid or self._get_network_field('ssid').strip('"')

    def getNetworkType(self):
        # 1 matches the P2P iface type used by the Android supplicant API.
        return 1

    def isNetworkCurrent(self):
        return self._refresh_active_p2p_connection(self.active_connection_name, self.active_peer)

    def isNetworkGroupOwner(self):
        self._refresh_group_status()
        if self.active_group_ifname:
            return self.active_is_go
        mode = self._get_network_field('mode')
        return mode == '3'

    def isNetworkPersistent(self):
        if self.active_connection_name and self._nm_connection_exists(self.active_connection_name):
            return True
        disabled = self._get_network_field('disabled')
        return disabled == '2'

    def setNetworkClientList(self, clients):
        self.active_client_list = clients or ""
        self._set_network_field('p2p_client_list', clients)

    def p2p_serv_disc_req(self, raw_args):
        output = self._run_p2p_command('p2p_serv_disc_req', *raw_args.split())
        return output or ""

    def p2p_serv_disc_cancel(self, identifier):
        self._run_p2p_expect_ok('p2p_serv_disc_cancel', identifier)

    def p2p_serv_disc_resp(self, raw_args):
        self._run_p2p_expect_ok('p2p_serv_disc_resp', *raw_args.split())

    def p2p_service_update(self):
        self._run_p2p_expect_ok('p2p_service_update')

    def p2p_serv_disc_external(self, value):
        self._run_p2p_expect_ok('p2p_serv_disc_external', value)

    def p2p_service_flush(self):
        self._run_p2p_expect_ok('p2p_service_flush')

    def p2p_service_rep(self, raw_args):
        self._run_p2p_expect_ok('p2p_service_rep', *raw_args.split())

    def p2p_service_del(self, raw_args):
        self._run_p2p_expect_ok('p2p_service_del', *raw_args.split())

    def p2p_reject(self, peer):
        self._run_p2p_expect_ok('p2p_reject', peer)

    def p2p_invite(self, raw_args):
        self._run_p2p_expect_ok('p2p_invite', *raw_args.split())

    def p2p_peers(self):
        output = self._run_p2p_command('p2p_peers')
        return output or ""

    def p2p_peer(self, peer):
        output = self._run_p2p_command('p2p_peer', peer)
        return output or ""

    def p2p_set(self, raw_args):
        args = raw_args.split() if raw_args else []
        if not args:
            logging.error("p2p_set called without arguments")
            return
        if args[0] in self.NM_IGNORED_P2P_SET_VARS:
            logging.info("Ignoring unsupported p2p_set %s under NetworkManager control", " ".join(args))
            return
        args[0] = self.P2P_SET_ALIASES.get(args[0], args[0])
        if args[0] in self.P2P_GLOBAL_CONFIG_VARS:
            self._run_p2p_expect_ok('set', *args)
        else:
            self._run_p2p_expect_ok('p2p_set', *args)

    def p2p_flush(self):
        self._run_p2p_expect_ok('p2p_flush')

    def p2p_unauthorize(self, peer):
        self._run_p2p_expect_ok('p2p_unauthorize', peer)

    def p2p_presence_req(self, raw_args):
        self._run_p2p_expect_ok('p2p_presence_req', *raw_args.split())

    def p2p_ext_listen(self, raw_args):
        self._run_p2p_expect_ok('p2p_ext_listen', *raw_args.split())

    def p2p_remove_client(self, raw_args):
        self._run_p2p_expect_ok('p2p_remove_client', *raw_args.split())

    def p2p_find(self, raw_args):
        self._run_p2p_expect_ok('p2p_find', *raw_args.split())

    def cleanup(self):
        self.interface = None


def start(args):
    def addBonjourService(query, response):
        initData['controller'].addBonjourService(query, response)

    def addGroup(persistent, persistentNetworkId):
        initData['controller'].addGroup(persistent, persistentNetworkId)

    def cancelConnect():
        initData['controller'].cancelConnect()

    def p2p_stop_find():
        initData['controller'].p2p_stop_find()

    def p2p_asp_provision(raw_args):
        initData['controller'].p2p_asp_provision(raw_args)

    def p2p_asp_provision_resp(raw_args):
        initData['controller'].p2p_asp_provision_resp(raw_args)

    def p2p_connect(raw_args):
        initData['controller'].p2p_connect(raw_args)

    def p2p_listen(raw_args):
        initData['controller'].p2p_listen(raw_args)

    def p2p_group_remove(ifname):
        initData['controller'].p2p_group_remove(ifname)

    def p2p_group_member(ifname):
        initData['controller'].p2p_group_member(ifname)

    def p2p_prov_disc(raw_args):
        initData['controller'].p2p_prov_disc(raw_args)

    def p2p_get_passphrase():
        return initData['controller'].p2p_get_passphrase()

    def p2p_serv_disc_req(raw_args):
        return initData['controller'].p2p_serv_disc_req(raw_args)

    def p2p_serv_disc_cancel(identifier):
        initData['controller'].p2p_serv_disc_cancel(identifier)

    def p2p_serv_disc_resp(raw_args):
        initData['controller'].p2p_serv_disc_resp(raw_args)

    def p2p_service_update():
        initData['controller'].p2p_service_update()

    def p2p_serv_disc_external(value):
        initData['controller'].p2p_serv_disc_external(value)

    def p2p_service_flush():
        initData['controller'].p2p_service_flush()

    def p2p_service_rep(raw_args):
        initData['controller'].p2p_service_rep(raw_args)

    def p2p_service_del(raw_args):
        initData['controller'].p2p_service_del(raw_args)

    def p2p_reject(peer):
        initData['controller'].p2p_reject(peer)

    def p2p_invite(raw_args):
        initData['controller'].p2p_invite(raw_args)

    def p2p_peers():
        return initData['controller'].p2p_peers()

    def p2p_peer(peer):
        return initData['controller'].p2p_peer(peer)

    def p2p_set(raw_args):
        initData['controller'].p2p_set(raw_args)

    def p2p_flush():
        initData['controller'].p2p_flush()

    def p2p_unauthorize(peer):
        initData['controller'].p2p_unauthorize(peer)

    def p2p_presence_req(raw_args):
        initData['controller'].p2p_presence_req(raw_args)

    def p2p_ext_listen(raw_args):
        initData['controller'].p2p_ext_listen(raw_args)

    def p2p_remove_client(raw_args):
        initData['controller'].p2p_remove_client(raw_args)

    def p2p_find(raw_args):
        initData['controller'].p2p_find(raw_args)

    def removeCallback(callback, reason="unknown"):
        global callbackData
        with callbackData['lock']:
            ret = False
            if callback in callbackData['registeredCallbacks']:
                callbackData['registeredCallbacks'].remove(callback)
                logging.info("P2P callback removed (%s). Remaining: %d",
                             reason, len(callbackData['registeredCallbacks']))
                ret = True

            if callback in callbackData['deathNotifications']:
                deathNotificationId = callbackData['deathNotifications'].pop(callback)
                try:
                    callback.remove_handler(deathNotificationId)
                except Exception as e:
                    logging.error("Failed to remove death notification: %s", e)
            return ret

    def registerCallback(callback):
        logging.info("P2P registerCallback: %s", callback)

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
                    logging.error("Failed to set up death notification: %s", e)
                return True
        logging.warning("P2P registerCallback called with no callback object")
        return False

    def unregisterCallback(callback):
        return removeCallback(callback, "clientUnregistered") if callback else False

    def p2p_get_device_address():
        return initData['controller'].p2p_get_device_address()

    def getNetworkBssid():
        return initData['controller'].getNetworkBssid()

    def getNetworkClientList():
        return initData['controller'].getNetworkClientList()

    def getNetworkId():
        return initData['controller'].getNetworkId()

    def getNetworkInterfaceName():
        return initData['controller'].getNetworkInterfaceName()

    def getNetworkSsid():
        return initData['controller'].getNetworkSsid()

    def getNetworkType():
        return initData['controller'].getNetworkType()

    def isNetworkCurrent():
        return initData['controller'].isNetworkCurrent()

    def isNetworkGroupOwner():
        return initData['controller'].isNetworkGroupOwner()

    def isNetworkPersistent():
        return initData['controller'].isNetworkPersistent()

    def setNetworkClientList(clients):
        initData['controller'].setNetworkClientList(clients)

    def network_service_thread():
        global initData
        while not initData['stopping']:
            if not initData['controller']:
                initData['controller'] = P2pController()
            ISupplicantP2pNetwork.add_service(
                args,
                getNetworkBssid,
                getNetworkClientList,
                getNetworkId,
                getNetworkInterfaceName,
                getNetworkSsid,
                getNetworkType,
                isNetworkCurrent,
                isNetworkGroupOwner,
                isNetworkPersistent,
                setNetworkClientList,
            )

    def service_thread():
        global initData
        while not initData['stopping']:
            if not initData['controller']:
                initData['controller'] = P2pController()
            IP2p.add_service(
                args,
                addBonjourService,
                addGroup,
                cancelConnect,
                p2p_stop_find,
                p2p_asp_provision,
                p2p_asp_provision_resp,
                p2p_connect,
                p2p_listen,
                p2p_group_remove,
                p2p_group_member,
                p2p_prov_disc,
                p2p_get_passphrase,
                p2p_serv_disc_req,
                p2p_serv_disc_cancel,
                p2p_serv_disc_resp,
                p2p_service_update,
                p2p_serv_disc_external,
                p2p_service_flush,
                p2p_service_rep,
                p2p_service_del,
                p2p_reject,
                p2p_invite,
                p2p_peers,
                p2p_peer,
                p2p_set,
                p2p_flush,
                p2p_unauthorize,
                p2p_presence_req,
                p2p_ext_listen,
                p2p_remove_client,
                p2p_find,
                registerCallback,
                unregisterCallback,
                p2p_get_device_address,
            )

    initData['stopping'] = False
    initData['monitor'] = P2pEventMonitor(dispatch_event)
    initData['monitor'].start()
    if not initData.get('network_service_started'):
        initData['network_service_started'] = True
        args.p2pNetworkManager = threading.Thread(target=network_service_thread)
        args.p2pNetworkManager.start()
    args.p2pManager = threading.Thread(target=service_thread)
    args.p2pManager.start()


def stop(args):
    global initData
    initData['stopping'] = True
    if initData['monitor']:
        initData['monitor'].stop()
        initData['monitor'] = None
    with callbackData['lock']:
        callbackData['registeredCallbacks'].clear()
        callbackData['deathNotifications'].clear()
    if initData['controller']:
        initData['controller'].cleanup()
        initData['controller'] = None
    try:
        if args.p2pLoop:
            args.p2pLoop.quit()
    except AttributeError:
        logging.debug("p2p service is not even started")
    try:
        if args.p2pNetworkLoop:
            args.p2pNetworkLoop.quit()
    except AttributeError:
        logging.debug("p2p network service is not even started")