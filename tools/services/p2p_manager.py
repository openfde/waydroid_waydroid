# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later

import binascii
import logging
import re
import subprocess
import threading

from tools.interfaces import IP2p, p2p_callback
from tools.services.p2p_monitor import P2pEventMonitor


initData = {
    'controller': None,
    'monitor': None,
    'stopping': False
}

callbackData = {
    'INTERFACE': p2p_callback.INTERFACE,
    'lock': threading.Lock(),
    'registeredCallbacks': [],
    'deathNotifications': {}
}


def dispatch_event(method_name, *args):
    """Invoke one ISupplicantP2pIfaceCallback method on every registered callback."""
    with callbackData['lock']:
        callbacks = list(callbackData['registeredCallbacks'])
    for callback in callbacks:
        try:
            if callback.is_dead():
                logging.warning("P2P callback is dead, skipping %s", method_name)
                continue
            proxy = p2p_callback.ISupplicantP2pIfaceCallback(callback)
            getattr(proxy, method_name)(*args)
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

    def __init__(self):
        self.interface = None

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
        command = ['p2p_group_add']
        if persistent:
            if persistentNetworkId >= 0:
                command.append(f'persistent={persistentNetworkId}')
            else:
                command.append('persistent')
        self._run_p2p_expect_ok(*command)

    def cancelConnect(self):
        self._run_p2p_expect_ok('p2p_cancel')

    def p2p_stop_find(self):
        self._run_p2p_expect_ok('p2p_stop_find')

    def p2p_asp_provision(self, raw_args):
        self._run_p2p_expect_ok('p2p_asp_provision', *raw_args.split())

    def p2p_asp_provision_resp(self, raw_args):
        self._run_p2p_expect_ok('p2p_asp_provision_resp', *raw_args.split())

    def p2p_connect(self, raw_args):
        self._run_p2p_expect_ok('p2p_connect', *raw_args.split())

    def p2p_listen(self, raw_args):
        args = raw_args.split() if raw_args else []
        self._run_p2p_expect_ok('p2p_listen', *args)

    def p2p_group_remove(self, ifname):
        self._run_p2p_expect_ok('p2p_group_remove', ifname)

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