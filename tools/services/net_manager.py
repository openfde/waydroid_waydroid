# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
"""
 1.The service to implement network-related interfaces
 2.add forgetWifi, getStaticIpConf; modify setStaticIp, setDHCP, getAllSsid, getActivedWifi, isWifiEnable
"""
import logging
import threading
import tools.actions.container_manager
import tools.actions.session_manager
import tools.config
import tools.helpers.run
import time

import subprocess


from tools import helpers
from tools.interfaces import INet

stopping = False
WifiStatusDisable = 0
WifiStatusEnable = 1
WifiStatusNoDevice = 2

def start(args):
    def run_nmcli_command(command):
        try:
            output = subprocess.check_output(command, shell=True, universal_newlines=True)
            if output:
                return output.strip()
            else:
                return "success"
        except subprocess.CalledProcessError as e:
            #logging.debug("Error executing nmcli command:", e)
            return None
    def setStaticIp(interfaceName, ipAddress, networkPrefixLength, gateway, dns1, dns2):
        logging.debug(
            "interfaceName: {}, ipAddress: {}, networkPrefixLength: {}, gateway: {}, dns1: {}, dns2: {}" \
            .format(interfaceName, ipAddress, networkPrefixLength, gateway, dns1, dns2))
        output = run_nmcli_command("nmcli con modify Openfde" + interfaceName + " ifname " + interfaceName + " ipv4.addresses " + ipAddress + "/" + str(networkPrefixLength) + " ipv4.gateway " + gateway + " ipv4.dns '" + dns1 + " " + dns2 + "' ipv4.method 'manual'")
        logging.debug(output)
        if not output:
            logging.debug("nmcli con add:")
            output = run_nmcli_command("nmcli con add con-name Openfde" + interfaceName + " ifname " + interfaceName + "  type ethernet ip4 " + ipAddress + "/" + str(networkPrefixLength) + " gw4 " + gateway + " ipv4.dns '" + dns1 + " " + dns2 + "' ipv4.method 'manual'")
        output = run_nmcli_command("nmcli connection up Openfde" + interfaceName)
        if output:
            logging.debug("set setStaticIp success")
            return 0
        else:
            logging.debug("set setStaticIp fail")
            return 1
    def setDHCP(interfaceName):
        logging.debug("interfaceName: {}".format(interfaceName))
        output = run_nmcli_command("nmcli con modify Openfde" + interfaceName + " ifname " + interfaceName + " ipv4.method 'auto'")
        logging.debug(output)
        if not output:
            logging.debug("nmcli con add:")
            output = run_nmcli_command("nmcli con add con-name Openfde" + interfaceName + " ifname " + interfaceName + " ipv4.method 'auto'")
        output = run_nmcli_command("nmcli connection up Openfde" + interfaceName)
        if output:
            logging.debug("set setDHCP success")
            return 0
        else:
            logging.debug("set setDHCP fail")
            return 1
    def getAllSsid():
        logging.debug("getAllSsid")
        output = run_nmcli_command("nmcli -t -f ssid,signal,security,in-use dev wifi")
        logging.debug(output)
        if output == "success":
            logging.debug("none any Ssid")
            return None
        elif output:
            logging.debug("getAllSsid success")
            return output
        else:
            logging.debug("getAllSsid fail")
            return None
    def connectSsid(ssid, passwd):
        logging.debug("ssid: {}, passwd: {}".format(ssid, passwd))
        output = run_nmcli_command("nmcli device wifi connect '" + ssid + "' password '" + passwd + "'")
        logging.debug(output)
        if output:
            logging.debug("connectSsid success")
            return 0
        else:
            logging.debug("connectSsid fail")
            return 1
    def getActivedWifi():
        output = run_nmcli_command("nmcli -g IN-USE,SSID device wifi|grep '*:'|sed -n 1p")
        logging.debug(output)
        if output:
            logging.debug("has ActivedWifi")
            return output[2:]
        else:
            logging.debug("no ActivedWifi")
            return None
    def connectActivedWifi(ssid, connect):
        logging.debug("ssid: {}, connect: {}".format(ssid, connect))
        if connect == 1:
            output = run_nmcli_command("nmcli dev wifi connect '" + ssid + "'")
        elif connect == 0:
            output = run_nmcli_command("nmcli connection down '" + ssid + "'")
        logging.debug(output)
        if output:
            logging.debug("connectActivedWifi success")
            return 0
        else:
            logging.debug("connectActivedWifi fail")
            return 1
    def enableWifi(enable):
        logging.debug("enable: {}".format(enable))
        if enable == 1:
            output = run_nmcli_command("nmcli radio wifi on")
        elif enable == 0:
            output = run_nmcli_command("nmcli radio wifi off")
        logging.debug(output)
        if output:
            logging.debug("enableWifi success")
            return 0
        else:
            logging.debug("enableWifi fail")
            return 1
    def connectedWifiList():
        output = run_nmcli_command("nmcli -g NAME,TYPE connection show|grep '802-11-wireless'|awk -F: '{print $1}'|sort -u")
        logging.debug(output)
        if output == "success":
            logging.debug("connectedWifiList success none")
            return None
        elif output:
            logging.debug("connectedWifiList success has")
            return output
        else:
            logging.debug("connectedWifiList fail")
            return None
    def isWifiEnable():
        output = run_nmcli_command("nmcli -g TYPE,STATE device status|grep wifi|grep 'wifi:unavailable'")
        logging.debug(output)
        if output == "wifi:unavailable":
            logging.debug("WifiStatusDisable")
            return WifiStatusDisable
        else:
            output = run_nmcli_command("nmcli -g TYPE,STATE device status|grep 'wifi:'")
            if output:
                logging.debug("WifiStatusEnable")
                return WifiStatusEnable
            else:
                logging.debug("WifiStatusNoDevice")
                return WifiStatusNoDevice
    def getSignalAndSecurity(ssid):
        output = run_nmcli_command("nmcli -g SSID,SIGNAL,SECURITY dev wifi|grep '" + ssid + "'|awk -F: '{print $2} {print $3}'")
        logging.debug(output)
        if output == "success":
            logging.debug("no SignalAndSecurity")
            return None
        elif output:
            logging.debug("has SignalAndSecurity")
            return output
        else:
            logging.debug("getSignalAndSecurity fail")
            return None
    def connectHidedWifi(ssid, passwd):
        logging.debug("ssid: {}, passwd: {}".format(ssid, passwd))

        output = run_nmcli_command("nmcli dev wifi connect '" + ssid + "' password '" + passwd + "' hidden yes")
        tryCount = 8
        logging.debug(output)
        while not output and tryCount != 0:
            time.sleep(2)
            output = run_nmcli_command("nmcli dev wifi connect '" + ssid + "' password '" + passwd + "' hidden yes")
            tryCount -= 1
            logging.debug("connectActivedWifi success")
        if output:
            logging.debug("connectHidedWifi success")
            return 0
        else:
            logging.debug("connectHidedWifi fail")
            return 1
    def forgetWifi(ssid):
        logging.debug("ssid: {}".format(ssid))
        output = run_nmcli_command("nmcli connection delete '" + ssid + "'")
        logging.debug(output)
        if output:
            logging.debug("forgetWifi success")
            return 0
        else:
            logging.debug("forgetWifi fail")
            return 1
    def getStaticIpConf(interfaceName):
        output = run_nmcli_command("nmcli -t -f ipv4.addresses,ipv4.gateway,ipv4.dns connection show Openfde" + interfaceName)
        logging.debug(output)
        if output == "success":
            logging.debug("no StaticIpConf")
            return None
        elif output:
            logging.debug("has StaticIpConf")
            return output
        else:
            logging.debug("getStaticIpConf fail")
            return None
    def service_thread():
        while not stopping:
            INet.add_service(
                args, setStaticIp, setDHCP, getAllSsid, connectSsid, getActivedWifi, connectActivedWifi, 
                enableWifi, connectedWifiList, isWifiEnable, getSignalAndSecurity, connectHidedWifi,
                forgetWifi, getStaticIpConf)

    global stopping
    stopping = False
    args.net_manager = threading.Thread(target=service_thread)
    args.net_manager.start()

def stop(args):
    global stopping
    stopping = True
    try:
        if args.netLoop:
            args.netLoop.quit()
    except AttributeError:
        logging.debug("net service is not even started")
