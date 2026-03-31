import os
import re

def versiontuple(v):
    return tuple(map(int, (v.split("."))))

def kernel_version():
    return tuple(map(int, re.match(r"(\d+)\.(\d+)", os.uname().release).groups()))

def is_kylin_v11():
    try:
        with open('/etc/os-release','r') as f:
            os_info = f.read().lower()
            return True if 'id=kylin' in os_info and 'version_id="v11"' in os_info else False
    except FileNotFoundError:
        try:
            with open('/etc/lsb-release','r') as f:
                os_info = f.read().lower()
                return True if 'distrib_id=kylin' in os_info and 'distrib_release=v11' in os_info else False
        except FileNotFoundError:
            return False
        


def is_target_os(target):
    try:
        with open('/etc/os-release','r') as f:
            os_info = f.read()
        for line in os_info.splitlines():
            if line.startswith("ID="):
                return line.split("=")[1].strip().lower() == target
        return False
    except FileNotFoundError:
        try:
            with open('/etc/lsb-release','r') as f:
                os_info = f.read()
            for line in os_info.splitlines():
                if line.startswith("DISTRIB_ID="):
                    return line.split("=")[1].strip().lower() == target
                return False
        except FileNotFoundError:
            return False