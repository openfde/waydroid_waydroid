# Copyright 2021 Erfan Abdi
# SPDX-License-Identifier: GPL-3.0-or-later
"""
 1.The service to implement network-related interfaces
 2.add forgetWifi, getStaticIpConf; modify setStaticIp, setDHCP, getAllSsid, getActivedWifi, isWifiEnable
 3.add getActivedInterface, getIpConfigure; modify return None to ''
 4.add getDns
 5.add getLans, getLansAndWlans, getLanAndWlanIpConfigurations
"""
import logging
import threading
import tools.actions.container_manager
import tools.actions.session_manager
import tools.config
import tools.helpers.run
import time
import json

import subprocess


from tools import helpers
from tools.interfaces import INet






def start(args):
    def run_nmcli_command(command):
        try:
            #logging.debug(command)
            output = subprocess.check_output(command, shell=True, universal_newlines=True)
            if output:
                return output.strip()
            else:
                return "success"
        except subprocess.CalledProcessError as e:
            #logging.debug("Error executing nmcli command:", e)
            return None
    def setStaticIp(interfaceName, ipAddress, networkPrefixLength, gateway, dns1, dns2):
        logging.verbose(
            "interfaceName: {}, ipAddress: {}, networkPrefixLength: {}, gateway: {}, dns1: {}, dns2: {}" \
            .format(interfaceName, ipAddress, networkPrefixLength, gateway, dns1, dns2))
        output = run_nmcli_command("nmcli con modify Openfde" + interfaceName + " ifname " + interfaceName + " ipv4.addresses " + ipAddress + "/" + str(networkPrefixLength) + " ipv4.gateway " + gateway + " ipv4.dns '" + dns1 + " " + dns2 + "' ipv4.method 'manual'")
        logging.verbose(output)
        if not output:
            logging.verbose("nmcli con add:")
            output = run_nmcli_command("nmcli con add con-name Openfde" + interfaceName + " ifname " + interfaceName + "  type ethernet ip4 " + ipAddress + "/" + str(networkPrefixLength) + " gw4 " + gateway + " ipv4.dns '" + dns1 + " " + dns2 + "' ipv4.method 'manual'")
        output = run_nmcli_command("nmcli connection up Openfde" + interfaceName)
        if output:
            logging.verbose("set setStaticIp success")
            return 0
        else:
            logging.debug("set setStaticIp fail")
            return 1
    def setDHCP(interfaceName):
        logging.verbose("interfaceName: {}".format(interfaceName))
        output = run_nmcli_command("nmcli con modify Openfde" + interfaceName + " ifname " + interfaceName + " ipv4.method 'auto'")
        logging.verbose(output)
        if not output:
            logging.verbose("nmcli con add:")
            output = run_nmcli_command("nmcli con add con-name Openfde" + interfaceName + " ifname " + interfaceName + " type ethernet ipv4.method 'auto'")
        output = run_nmcli_command("nmcli connection up Openfde" + interfaceName)
        if output:
            logging.verbose("set setDHCP success")
            return 0
        else:
            logging.debug("set setDHCP fail")
            return 1
    def getAllSsid():
        logging.verbose("getAllSsid")
        output = run_nmcli_command("nmcli -t -f ssid,signal,security,in-use dev wifi")
        logging.verbose(output)
        if output == "success":
            logging.verbose("none any Ssid")
            return ""
        elif output:
            logging.verbose("getAllSsid success")
            return output
        else:
            logging.debug("getAllSsid fail")
            return ""
    def connectSsidThread(ssid, passwd):
        logging.verbose("ssid: {}, passwd: {}".format(ssid, passwd))
        output = run_nmcli_command("nmcli device wifi connect '" + ssid + "' password '" + passwd + "'")
        logging.verbose(output)
        if output:
            logging.verbose("connectSsid success")
            return 0
        else:
            logging.debug("connectSsid fail")
            return 1
    def connectSsid(ssid, passwd):
        threading.Thread(target=connectSsidThread, args=(ssid, passwd)).start()
        return 0
    def getActivedWifi():
        output = run_nmcli_command("nmcli -g IN-USE,SSID device wifi|grep '*:'|sed -n 1p")
        logging.verbose(output)
        if (output == "success") or not output:
            logging.verbose("no ActivedWifi")
            return ""
        else:
            logging.verbose("has ActivedWifi")
            return output[2:]
    def connectActivedWifi(ssid, connect):
        logging.verbose("ssid: {}, connect: {}".format(ssid, connect))
        if connect == 1:
            output = run_nmcli_command("nmcli dev wifi connect '" + ssid + "'")
        elif connect == 0:
            output = run_nmcli_command("nmcli connection down '" + ssid + "'")
        logging.verbose(output)
        if output:
            logging.verbose("connectActivedWifi success")
            return 0
        else:
            logging.debug("connectActivedWifi fail")
            return 1
    def enableWifi(enable):
        logging.verbose("enable: {}".format(enable))
        if enable == 1:
            output = run_nmcli_command("nmcli radio wifi on")
        elif enable == 0:
            output = run_nmcli_command("nmcli radio wifi off")
        logging.verbose(output)
        if output:
            logging.verbose("enableWifi success")
            return 0
        else:
            logging.debug("enableWifi fail")
            return 1
    def connectedWifiList():
        output = run_nmcli_command("nmcli -g NAME,TYPE connection show|grep '802-11-wireless'|awk -F: '{print $1}'|sort -u")
        logging.verbose(output)
        if output == "success":
            logging.verbose("connectedWifiList success none")
            return ""
        elif output:
            logging.verbose("connectedWifiList success has")
            return output
        else:
            logging.debug("connectedWifiList fail")
            return ""
    def isWifiEnable():
        output = run_nmcli_command("nmcli -g TYPE,STATE device status|grep wifi|grep 'wifi:unavailable'")
        logging.verbose(output)
        if output == "wifi:unavailable":
            logging.verbose("WifiStatusDisable")
            return WifiStatusDisable
        else:
            output = run_nmcli_command("nmcli -g TYPE,STATE device status|grep 'wifi:'")
            if output:
                logging.verbose("WifiStatusEnable")
                return WifiStatusEnable
            else:
                logging.verbose("WifiStatusNoDevice")
                return WifiStatusNoDevice
    def getSignalAndSecurity(ssid):
        output = run_nmcli_command("nmcli -g SSID,SIGNAL,SECURITY dev wifi|grep '" + ssid + "'|awk -F: '{print $2} {print $3}'")
        logging.verbose(output)
        if output == "success":
            logging.debug("no SignalAndSecurity")
            return ""
        elif output:
            logging.verbose("has SignalAndSecurity")
            return output
        else:
            logging.debug("getSignalAndSecurity fail")
            return ""
    def connectHidedWifi(ssid, passwd):
        logging.verbose("ssid: {}, passwd: {}".format(ssid, passwd))

        output = run_nmcli_command("nmcli dev wifi connect '" + ssid + "' password '" + passwd + "' hidden yes")
        tryCount = 8
        logging.verbose(output)
        while not output and tryCount != 0:
            time.sleep(2)
            output = run_nmcli_command("nmcli dev wifi connect '" + ssid + "' password '" + passwd + "' hidden yes")
            tryCount -= 1
            logging.verbose("connectActivedWifi success")
        if output:
            logging.verbose("connectHidedWifi success")
            return 0
        else:
            logging.debug("connectHidedWifi fail")
            return 1
    def forgetWifi(ssid):
        logging.verbose("ssid: {}".format(ssid))
        output = run_nmcli_command("nmcli connection delete '" + ssid + "'")
        logging.verbose(output)
        if output:
            logging.verbose("forgetWifi success")
            return 0
        else:
            logging.debug("forgetWifi fail")
            return 1
    def getStaticIpConf(interfaceName):
        output = run_nmcli_command("nmcli -t -f ipv4.addresses,ipv4.gateway,ipv4.dns connection show Openfde" + interfaceName)
        logging.verbose(output)
        if output == "success":
            logging.verbose("no StaticIpConf")
            return ""
        elif output:
            logging.verbose("has StaticIpConf")
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
            logging.verbose("getOneActivedEthernet: " + output)
            return output
        else :
            logging.debug("getOneActivedEthernet fail")
            return ""
    def getIpConfigure(interfaceName):
        activedConf = run_nmcli_command("nmcli -g type,device,name connection show --active|grep '802-3-ethernet:" + interfaceName + ":'|awk -F: '{print$3}'")
        error = '{"code": -1}'
        noIpUnlink = '{"code": 0,"status": "unlink"}'
        noIpLink = '{"code": 0,"status": "link"}'
        if activedConf == "success":
            logging.debug("getOneActivedEthernet null")
            allConf = run_nmcli_command("nmcli -g type,name connection show|grep '802-3-ethernet:'|awk -F: '{print $2}'")
            if allConf == "success":
                logging.debug("Configure null")
                return noIpUnlink
            elif allConf:
                logging.verbose("allConf: " + allConf)
                allConfForInterfaceList = []
                for conf in allConf.split('\n'):
                    if interfaceName == run_nmcli_command("nmcli -g connection.interface-name connection show '" + conf + "'"):
                        allConfForInterfaceList.append(conf)
                if not allConfForInterfaceList:
                    return noIpUnlink
                latestTimestamp = 0
                index = -1
                for i, conf in enumerate(allConfForInterfaceList):
                    timestamp = run_nmcli_command("nmcli -g connection.timestamp connection show '" + conf + "'")
                    if latestTimestamp < int(timestamp):
                        latestTimestamp = int(timestamp)
                        index = i
                if index == -1:
                    logging.debug("get ipConfigure null ")
                    return noIpUnlink
                method = run_nmcli_command("nmcli -g ipv4.method connection show '" + allConfForInterfaceList[index] + "'")
                if method == "auto":
                    return '{"code": 1,"status": "unlink","method": "auto"}'
                elif method == "manual":
                    address = run_nmcli_command("nmcli -g ipv4.addresses connection show '" + allConfForInterfaceList[index] + "'")
                    gateway = run_nmcli_command("nmcli -g ipv4.gateway connection show '" + allConfForInterfaceList[index] + "'")
                    dns = run_nmcli_command("nmcli -g ipv4.dns connection show '" + allConfForInterfaceList[index] + "'")
                    return '{"code": 1,"status": "unlink","method": "manual"' \
                            + ',"address": ' + '"' + (address if address and address != "success" else '') + '"' \
                            + ',"gateway": ' + '"' + (gateway if gateway and gateway != "success" else '') + '"' \
                            + ',"dns": ' + '"' + (dns.replace(',', ' | ') if dns and dns != "success" else '') + '"' \
                            + '}'
                else :
                    logging.debug("get method fail ")
                    return noIpUnlink
            else :
                logging.debug("allConf: fail")
                return noIpUnlink
        elif activedConf:
            logging.verbose("getOneActivedEthernetIpConfigure: " + activedConf)
            ipConfigure = run_nmcli_command("nmcli -g ipv4.method,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS connection show '" + activedConf + "'")
            if ipConfigure and ipConfigure != "success":
                keys = ["code", "status", "method", "address", "gateway", "dns"]
                values = [1, "link"] + ipConfigure.split('\n')
                resultDict = {key: value for key, value in zip(keys, values)}
                logging.verbose(resultDict)
                jsonStr = json.dumps(resultDict)
                logging.verbose(jsonStr)
                return jsonStr
            else :
                logging.debug("getUsingIpConfigure: fail")
                return noIpLink
        else :
            logging.debug("getOneActivedEthernet fail")
            return error
    def getDns(interfaceName):
        conProfile = run_nmcli_command("nmcli -g device,name connection show --active |grep '" + interfaceName + ":'|awk -F: '{print$2}'")
        logging.verbose(conProfile)
        if conProfile == "success":
            logging.debug(interfaceName + "not actived")
            return ""
        elif conProfile:
            outDns = run_nmcli_command("nmcli -g IP4.DNS connection show " + conProfile)
            if outDns == "success":
                logging.debug("no Dns")
                return ""
            elif outDns:
                logging.verbose("has Dns")
                return outDns
            else:
                logging.debug("getDns fail")
                return ""
        else:
            logging.debug("getDns fail")
            return ""
    def getLans():
        physicalEthernets = run_nmcli_command('''nmcli -g device,type device status |grep ':ethernet'|awk -F: '{print$1}' | grep -v "`ls /sys/devices/virtual/net/`"''')
        if physicalEthernets == "success":
            logging.debug("getLans: null")
            return ""
        elif physicalEthernets:
            logging.verbose("getLans: " + physicalEthernets)
            return physicalEthernets
        else :
            logging.debug("getLans fail")
            return ""
    def getLansAndWlans():
        physicalEthernets = getLans()
        physicalWlans = run_nmcli_command("nmcli -g device,type device status |grep ':wifi'|grep -v ':wifi-p2p'|awk -F: '{print$1}'")
        if physicalWlans == "success":
            # logging.debug("physicalWlans: null")
            physicalWlans = ''
        elif physicalWlans:
            logging.verbose("physicalWlans: " + physicalWlans)
        else :
            logging.debug("physicalWlans fail")
            physicalWlans = ''
        if physicalEthernets != '' and physicalWlans != '':
            return physicalEthernets + '\n' + physicalWlans
        elif physicalEthernets != '':
            return physicalEthernets
        elif physicalWlans != '':
            return physicalWlans
        else :
            return ""
    def getLanAndWlanIpConfigurations():
        ret = ''
        physicalLans = run_nmcli_command('''nmcli -g device,type device status |grep ':ethernet'|awk -F: '{print$1}' | grep -v "`ls /sys/devices/virtual/net/`"''')
        if physicalLans == "success":
            # logging.debug("physicalLans: null")
        elif physicalLans:
            logging.verbose("physicalLans: " + physicalLans)
            physicalLansList = physicalLans.split('\n')
            lanCounts = len(physicalLansList)
            i = 0
            ipConfigurationsList = []
            while i < lanCounts:
                #logging.debug("physicalLansList: " + str(i) + " :" + physicalLansList[i])
                ipConfiguration = run_nmcli_command("nmcli -g IP4.ADDRESS,IP4.GATEWAY,IP4.DNS device show " + physicalLansList[i])
                if ipConfiguration == "success":
                    logging.debug("Lancon: null")
                elif ipConfiguration:
                    ipConfigurationsList.append(physicalLansList[i] + "#" + ipConfiguration.replace('\n', '#'))
                else :
                    logging.debug("Lancon: error")
                i += 1
            ipConfigurationCounts = len(ipConfigurationsList)
            j = 0
            while j < ipConfigurationCounts:
                #logging.debug("ipConfiguration: " + str(j) + " :" + ipConfigurationsList[j])
                if j != 0:
                    ret = ret + ';' + ipConfigurationsList[j]
                else :
                    ret = ipConfigurationsList[j]
                j += 1
        else :
            logging.debug("physicalLans fail")
        physicalWlans = run_nmcli_command("nmcli -g device,type device status |grep ':wifi'|grep -v ':wifi-p2p'|awk -F: '{print$1}'")
        if physicalWlans == "success":
            logging.debug("no wlan")
        elif physicalWlans:
            logging.verbose("physicalWlans: " + physicalWlans)
            physicalWlansList = physicalWlans.split('\n')
            wlanCounts = len(physicalWlansList)
            i = 0
            ipConfigurationsList = []
            while i < wlanCounts:
                #logging.debug("physicalWlansList: " + str(i) + " :" + physicalWlansList[i])
                ipConfiguration = run_nmcli_command("nmcli -g IP4.ADDRESS,IP4.GATEWAY,IP4.DNS device show " + physicalWlansList[i])
                if ipConfiguration == "success":
                    logging.debug("Wlancon: null")
                elif ipConfiguration:
                    ipConfigurationsList.append(physicalWlansList[i] + "#" + ipConfiguration.replace('\n', '#'))
                else :
                    logging.debug("Wlancon: error")
                i += 1
            ipConfigurationCounts = len(ipConfigurationsList)
            j = 0
            while j < ipConfigurationCounts:
                #logging.debug("ipConfiguration: " + str(j) + " :" + ipConfigurationsList[j])
                if j != 0 or ret != '':
                    ret = ret + ';' + ipConfigurationsList[j]
                else :
                    ret = ipConfigurationsList[j]
                j += 1
        else :
            logging.debug("physicalWlans error")
        return ret
    def ipConfiged(interface):
        ipConfiguration = run_nmcli_command("nmcli -g IP4.ADDRESS,IP4.GATEWAY,IP4.DNS device show " + interface)
        if ipConfiguration == "success":
            logging.debug("ipConfiged: null")
            return 0
        elif ipConfiguration:
            logging.verbose("ipConfiged: ok")
            return 1
        else :
            logging.debug("ipConfiged: error")
            return 0
    def getLansWlansBridges():
        wlansEthernets = getLansAndWlans()
        if wlansEthernets == "":
            return ""
        bridges = run_nmcli_command("nmcli -g device,type device status |grep ':bridge'|awk -F: '{print$1}'")
        if bridges == "success":
            logging.verbose("getBridges: null")
            return wlansEthernets
        elif bridges:
            logging.verbose("getBridges: " + bridges)
            wlansEthernetsBridges = wlansEthernets
            for bridge in bridges.split('\n'):
                bridgeHwaddr = run_nmcli_command("nmcli -g general.hwaddr device show " + bridge)
                for wlanEthernet in wlansEthernets.split('\n'):
                    wlanEthernetHwaddr = run_nmcli_command("nmcli -g general.hwaddr device show " + wlanEthernet)
                    if bridgeHwaddr == wlanEthernetHwaddr:
                        wlansEthernetsBridges = wlansEthernetsBridges + "\n" + bridge
            logging.verbose("wlansEthernetsBridges: " + wlansEthernetsBridges)
            return wlansEthernetsBridges
        else :
            logging.debug("getBridges fail")
            return wlansEthernets
    def getLanWlanBridgeIpConfigurations():
        ret = ''
        lansWlansBridges = getLansWlansBridges()
        if lansWlansBridges == '':
            return ret
        for dev in lansWlansBridges.split('\n'):
            ipConfiguration = run_nmcli_command("nmcli -g IP4.ADDRESS,IP4.GATEWAY,IP4.DNS device show " + dev)
            if ipConfiguration == "success" or ipConfiguration == "":
                logging.verbose("ipConf: null")
            elif ipConfiguration:
                ret = ret + ("" if ret == "" else ";") + dev + "#" + ipConfiguration.replace('\n', '#')
            else :
                logging.debug("ipConf: error")
        return ret
    def getAllSsidInfo():
        logging.verbose("getAllSsidInfo")
        allSsidInfo = run_nmcli_command("nmcli -t -f ssid,signal,security,in-use dev wifi")
        logging.verbose(allSsidInfo)
        if allSsidInfo == "success":
            logging.verbose("none any Ssid")
            return ""
        elif allSsidInfo:
            logging.verbose("getAllSsid success")
            allConnectedSsid = run_nmcli_command("nmcli -g NAME,TYPE connection show|grep '802-11-wireless'|awk -F: '{print $1}'|sort -u")
            logging.verbose(allConnectedSsid)
            if allConnectedSsid == "success":
                logging.verbose("none any ConnectedSsid")
                return allSsidInfo
            elif allConnectedSsid:
                logging.verbose("AllConnectedSsid: \n" + allConnectedSsid)
                newAllSsidInfo = ''
                for info in allSsidInfo.split('\n'):
                    find = False
                    for ssid in allConnectedSsid.split('\n'):
                        if info.startswith(ssid + ':'):
                            find = True
                            break
                    info = info.strip()
                    if find and not info.endswith(":*"):
                        info = info + "**"
                    newAllSsidInfo = newAllSsidInfo + (info if newAllSsidInfo == '' else '\n' + info)
                return newAllSsidInfo
            else:
                logging.debug("getAllConnectedSsid fail")
                return ""
        else:
            logging.debug("getAllSsid fail")
            return ""
    def service_thread():
        while not stopping:
            INet.add_service(
                args, setStaticIp, setDHCP, getAllSsid, connectSsid, getActivedWifi, connectActivedWifi, 
                enableWifi, connectedWifiList, isWifiEnable, getSignalAndSecurity, connectHidedWifi, 
                forgetWifi, getStaticIpConf, getActivedInterface, getIpConfigure, getDns, getLans, 
                getLansAndWlans, getLanAndWlanIpConfigurations, ipConfiged, getLansWlansBridges,
                getLanWlanBridgeIpConfigurations, getAllSsidInfo)

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
