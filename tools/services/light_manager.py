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
import subprocess
import os
import re

from tools.interfaces import ILight

gStopping = False
gInitData = {
    "userMinBrightness": 1,
    "systemMinBrightness": 0,
    "userMaxBrightness": 255,
    "userMaxBrightnessFloat": 255.0,
    "ddDefaultMaxBrightness": 100,
    "sysDefaultMaxBrightness": 255,
    "sysfs": False,
    "ddcutil": False,
    "devices": [],
    "busNum": [],
    "ddMaxBrightness": [],
    "sysMaxBrightness": []
}

def start(args):
    def parseDdcutilDisplays(output: str) -> bool:
        global gInitData
        for line in output.splitlines():
            if line.strip().startswith('I2C bus'):
                gInitData["busNum"].append(line.strip().split('-')[-1])
        gInitData["ddMaxBrightness"] = [ddcutilGetMaxBrightness(b) for b in gInitData["busNum"]]
        gInitData["ddcutil"] = len(gInitData["busNum"]) > 0
        return gInitData["ddcutil"]

    def getSysfsInfo() -> bool:
        backlightPath = "/sys/class/backlight"
        global gInitData
        if not os.path.exists(backlightPath):
            logging.error("no /sys/class/backlight")
            return False
        try:
            gInitData["devices"] = [d for d in os.listdir(backlightPath) if os.path.isdir(os.path.join(backlightPath, d))]
            gInitData["sysMaxBrightness"] = [sysfsGetMaxBrightness(d) for d in gInitData["devices"]]
            gInitData["sysfs"] = len(gInitData["devices"]) > 0
            return gInitData["sysfs"]
        except (OSError, PermissionError) as e:
            logging.error(f"getSysfsInfo fail: {e}")
            return False

    def getDdcutilInfo() -> bool:
        try:
            result = subprocess.run(['ddcutil', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                detectResult = subprocess.run(['ddcutil', 'detect'], capture_output=True, text=True, timeout=30)
                if detectResult.returncode == 0:
                    return parseDdcutilDisplays(detectResult.stdout)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError) as e:
            logging.error(f"detectDdcutil fail: {e}")
        return False

    def userToSystem(userValue: int, systemMax: int) -> int:
        if systemMax <= gInitData["systemMinBrightness"]:
            return gInitData["systemMinBrightness"]
        return int(round(((userValue - gInitData["userMinBrightness"]) / (gInitData["userMaxBrightnessFloat"] - gInitData["userMinBrightness"])) * systemMax))

    def systemToUser(systemValue: int, systemMax: int) -> int:
        if systemMax <= gInitData["systemMinBrightness"]:
            return gInitData["userMinBrightness"]
        return int(round((systemValue / systemMax) * (gInitData["userMaxBrightnessFloat"] - gInitData["userMinBrightness"]) + gInitData["userMinBrightness"]))

    def validateUserValue(value: int) -> bool:
        return gInitData["userMinBrightness"] <= value <= gInitData["userMaxBrightness"]

    def sysfsGetBacklightRaw(device: str) -> int:
        try:
            brightnessPath = f"/sys/class/backlight/{device}/brightness"
            with open(brightnessPath, 'r') as f:
                return int(f.read().strip())
        except (OSError, ValueError, PermissionError) as e:
            logging.error(f"sysfsGetBacklightRaw fail: {e}")
            return gInitData["systemMinBrightness"]

    def sysfsSetBacklightRaw(device: str, value: int) -> bool:
        try:
            brightnessPath = f"/sys/class/backlight/{device}/brightness"
            with open(brightnessPath, 'w') as f:
                f.write(str(value))
            return True
        except (OSError, PermissionError) as e:
            logging.error(f"sysfsSetBacklightRaw fail: {e}")
            return False

    def sysfsGetMaxBrightness(device: str) -> int:
        try:
            maxBrightnessPath = f"/sys/class/backlight/{device}/max_brightness"
            with open(maxBrightnessPath, 'r') as f:
                return int(f.read().strip())
        except (OSError, ValueError, PermissionError) as e:
            logging.error(f"can not get MaxBrightness: {e}")
            return gInitData["userMaxBrightnessInt"]

    def ddcutilGetBacklightRaw(busNum: str) -> int:
        try:
            cmd = ['ddcutil', '-b', busNum, 'getvcp', '10']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logging.error(f"ddcutil exec fail: {result.stderr}")
                return gInitData["systemMinBrightness"]

            # "VCP code 0x10 (Brightness                    ): current value =    56, max value =   100"
            # "VCP 10 (Brightness): current value = 75, max value = 100"
            patterns = [
                r'current value =\s*(\d+)',
                r'current value\s*=\s*(\d+)',
                r':\s*(\d+),\s*max'
            ]

            for pattern in patterns:
                match = re.search(pattern, result.stdout)
                if match:
                    return int(match.group(1))
            logging.error(f"resolve ddcutil fail，rawoutput: {result.stdout.strip()}")
            return gInitData["systemMinBrightness"]
        except subprocess.TimeoutExpired:
            logging.error("ddcutil exec tomeout")
            return gInitData["systemMinBrightness"]

    def ddcutilSetBacklightRaw(busNum: str, value: int) -> bool:
        try:
            cmd = ['ddcutil', '-b', busNum, 'setvcp', '10', str(value)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logging.error(f"ddcutil set fail: {result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logging.error("ddcutil exec tomeout")
            return False

    def ddcutilGetMaxBrightness(busNum: str) -> int:
        try:
            cmd = ['ddcutil', '-b', busNum, 'getvcp', '10']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logging.error(f"ddcutil exec fail: {result.stderr}")
                return gInitData["ddDefaultMaxBrightness"]

            maxMatch = re.search(r'max value = (\d+)', result.stdout)
            if maxMatch:
                maxValue = int(maxMatch.group(1))
                return maxValue
            else:
                return gInitData["ddDefaultMaxBrightness"]
        except subprocess.TimeoutExpired:
            logging.error("ddcutil exec timeout!")
            return gInitData["ddDefaultMaxBrightness"]

    def getBacklight() -> int:
        if gInitData["sysfs"]:
            return systemToUser(sysfsGetBacklightRaw(gInitData["devices"][0]), gInitData["sysMaxBrightness"][0])
        elif gInitData["ddcutil"]:
            return systemToUser(ddcutilGetBacklightRaw(gInitData["busNum"][0]), gInitData["ddMaxBrightness"][0])
        return 0

    def setBacklight(value: int) -> int:
        if not validateUserValue(value):
            logging.error(f"Backlight must be 1-255: {value}")
            return 0
        if gInitData["sysfs"]:
            for i in range(len(gInitData["devices"])):
                sysfsSetBacklightRaw(gInitData["devices"][i], userToSystem(value, gInitData["sysMaxBrightness"][i]))
        if gInitData["ddcutil"]:
            for i in range(len(gInitData["busNum"])):
                ddcutilSetBacklightRaw(gInitData["busNum"][i], userToSystem(value, gInitData["ddMaxBrightness"][i]))
        return 0

    def lightInit():
        getSysfsInfo()
        getDdcutilInfo()

    def service_thread():
        while not gStopping:
            ILight.add_service(args, lightInit, setBacklight, getBacklight)

    global gStopping
    gStopping = False
    args.light_manager = threading.Thread(target=service_thread)
    args.light_manager.start()

def stop(args):
    global gStopping
    gStopping = True
    try:
        if args.lightLoop:
            args.lightLoop.quit()
    except AttributeError:
        logging.debug("light service is not even started")
