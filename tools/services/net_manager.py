# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
"""
 1.The service to implement network-related interfaces
 2.add forgetWifi, getStaticIpConf; modify setStaticIp, setDHCP, getAllSsid, getActivedWifi, isWifiEnable
 3.add getActivedInterface, getIpConfigure; modify return None to ''
 4.add getDns
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
            output = run_nmcli_command("nmcli con add con-name Openfde" + interfaceName + " ifname " + interfaceName + " type ethernet ipv4.method 'auto'")
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
            return ""
        elif output:
            logging.debug("getAllSsid success")
            return output
        else:
            logging.debug("getAllSsid fail")
            return ""
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
            return ""
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
            return ""
        elif output:
            logging.debug("connectedWifiList success has")
            return output
        else:
            logging.debug("connectedWifiList fail")
            return ""
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
            return ""
        elif output:
            logging.debug("has SignalAndSecurity")
            return output
        else:
            logging.debug("getSignalAndSecurity fail")
            return ""
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
            return ""
        elif output:
            logging.debug("has StaticIpConf")
            return output
        else:
            logging.debug("getStaticIpConf fail")
            return ""
    def getActivedInterface():
        output = run_nmcli_command("nmcli -g type,device connection show --active|grep '802-3-ethernet:'|sed -n 1p|awk -F: '{print$2}'")
        if output == "success":
            logging.debug("getOneActivedEthernet: null")
            return ""
        elif output:
            logging.debug("getOneActivedEthernet: " + output)
            return output
        else :
            logging.debug("getOneActivedEthernet fail")
            return ""
    def getIpConfigure(interfaceName):
        activedConf = run_nmcli_command("nmcli -g type,device,name connection show --active|grep '802-3-ethernet:" + interfaceName + ":'|awk -F: '{print$3}'")
        if activedConf == "success":
            logging.debug("getOneActivedEthernet null")
            allConf = run_nmcli_command("nmcli -g type,name connection show|grep '802-3-ethernet:'|awk -F: '{print $2}'")
            if allConf == "success":
                logging.debug("Configure null")
                return ""
            elif allConf:
                logging.debug("allConf: " + allConf)
                allConfList = allConf.split('\n')
                confCounts = len(allConfList)
                i = 0
                allConfForInterfaceList = []
                while i < confCounts:
                    if interfaceName == run_nmcli_command("nmcli -g connection.interface-name connection show '" + allConfList[i] + "'"):
                        allConfForInterfaceList.append(allConfList[i])
                    i += 1
                confForInterfaceCounts = len(allConfForInterfaceList)
                j = 0
                latestTimestamp = 0
                index = -1
                while j < confForInterfaceCounts:
                    timestamp = run_nmcli_command("nmcli -g connection.timestamp connection show '" + allConfForInterfaceList[j] + "'")
                    if latestTimestamp < int(timestamp):
                        latestTimestamp = int(timestamp)
                        index = j
                    j += 1
                if index == -1:
                    logging.debug("get ipConfigure null ")
                    return ""
                ipConfigure = run_nmcli_command("nmcli -g ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns connection show '" + allConfForInterfaceList[index] + "'")
                if ipConfigure:
                    logging.debug("get ipConfigure: " + ipConfigure)
                    return ipConfigure
                else :
                    logging.debug("get ipConfigure fail ")
                    return ""
            else :
                logging.debug("allConf: fail")
                return ""
        elif activedConf:
            logging.debug("getOneActivedEthernetIpConfigure: " + activedConf)
            return run_nmcli_command("nmcli -g ipv4.method,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS connection show '" + activedConf + "'")
        else :
            logging.debug("getOneActivedEthernet fail")
            return ""
    def getDns(interfaceName):
        conProfile = run_nmcli_command("nmcli -g device,name connection show --active |grep '" + interfaceName + ":'|awk -F: '{print$2}'")
        logging.debug(conProfile)
        if conProfile == "success":
            logging.debug(interfaceName + "not actived")
            return ""
        elif conProfile:
            outDns = run_nmcli_command("nmcli -g IP4.DNS connection show " + conProfile)
            if outDns == "success":
                logging.debug("no Dns")
                return ""
            elif outDns:
                logging.debug("has Dns")
                return outDns
            else:
                logging.debug("getDns fail")
                return ""
        else:
            logging.debug("getDns fail")
            return ""
    def service_thread():
        while not stopping:
            INet.add_service(
                args, setStaticIp, setDHCP, getAllSsid, connectSsid, getActivedWifi, connectActivedWifi, 
                enableWifi, connectedWifiList, isWifiEnable, getSignalAndSecurity, connectHidedWifi, 
                forgetWifi, getStaticIpConf, getActivedInterface, getIpConfigure, getDns)

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
